#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_workspace_folder_management.py
@Author  : caixiongjiang
@Date    : 2026/02/16
@Function: 
    测试 WorkspaceFolder + WorkspaceFileSystem 的复杂文件夹管理能力
    
    模拟以下场景：
    1. 构建多级文件夹结构（根目录 → 子文件夹 → 孙文件夹）
    2. 上传文件到不同文件夹和根目录
    3. 查询文件夹树、子文件夹、某文件夹下的文件
    4. 文件移动（从一个文件夹移到另一个）
    5. 文件夹重命名（更新 full_path 及所有后代路径）
    6. 文件夹移动（改变父文件夹，更新后代路径）
    7. 级联删除文件夹（文件夹 + 子文件夹 + 文件夹下所有文件）
    8. 多知识库隔离验证
    
    数据清理说明：
    - 默认测试后保留数据供数据库检查
    - 每次运行前会自动物理删除上次的残留数据
    - 加 --cleanup 参数可在测试后物理删除数据
    
    使用示例：
    # 正常运行（测试后保留数据供检查）
    uv run python test/db/mysql/test_workspace_folder_management.py
    
    # 测试后自动清理数据
    uv run python test/db/mysql/test_workspace_folder_management.py --cleanup
    
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import os
import uuid
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 测试常量
TEST_USER_ID = "test_folder_user_001"
TEST_KB_ID_A = "kb_test_a"
TEST_KB_ID_B = "kb_test_b"
TEST_KB_NAME_A = "测试知识库A"
TEST_KB_NAME_B = "测试知识库B"
TEST_CREATOR = "folder_test"


def gen_folder_id() -> str:
    """生成文件夹 ID"""
    return f"fld_{uuid.uuid4().hex[:12]}"


def gen_file_id() -> str:
    """生成文件 ID"""
    return f"file_{uuid.uuid4().hex[:12]}"


# ==================== 辅助函数 ====================


def print_folder_tree(folders: list, files: list, indent: str = "") -> None:
    """打印文件夹树结构（仅用于调试输出）
    
    空文件夹（无子文件夹且无文件）会标记 (空) 以示其独立存在。
    """
    folder_map: dict = {}
    for f in folders:
        parent_id = f.parent_folder_id
        if parent_id not in folder_map:
            folder_map[parent_id] = []
        folder_map[parent_id].append(f)
    
    file_map: dict = {}
    for f in files:
        fid = f.folder_id
        if fid not in file_map:
            file_map[fid] = []
        file_map[fid].append(f)
    
    def _print_node(parent_id: str | None, prefix: str) -> None:
        child_folders = folder_map.get(parent_id, [])
        child_folders.sort(key=lambda x: x.sort_order)
        parent_files = file_map.get(parent_id, [])
        
        items_total = len(child_folders) + len(parent_files)
        item_idx = 0
        
        for folder in child_folders:
            item_idx += 1
            is_last = item_idx == items_total
            connector = "└── " if is_last else "├── "
            
            has_children = folder.folder_id in folder_map
            has_files = folder.folder_id in file_map
            empty_tag = " (空)" if not has_children and not has_files else ""
            
            print(f"    {prefix}{connector}[{folder.folder_name}/]{empty_tag}")
            
            sub_prefix = prefix + ("    " if is_last else "│   ")
            _print_node(folder.folder_id, sub_prefix)
        
        for file_obj in parent_files:
            item_idx += 1
            is_last = item_idx == items_total
            connector = "└── " if is_last else "├── "
            print(f"    {prefix}{connector}{file_obj.file_name}")
    
    _print_node(None, indent)


# ==================== 测试用例 ====================


def test_build_folder_structure():
    """测试1: 构建多级文件夹结构
    
    目标结构（知识库A）:
    / (根目录)
    ├── 技术文档/              (depth=0)
    │   ├── 前端/              (depth=1)
    │   │   └── React/         (depth=2)
    │   └── 后端/              (depth=1)
    └── 产品设计/              (depth=0)
    """
    print("\n" + "=" * 70)
    print("测试1: 构建多级文件夹结构")
    print("=" * 70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.business import workspace_folder_repo
    
    manager = get_mysql_manager("mysql")
    manager.init_db()
    
    folder_ids = {}
    
    with manager.get_session() as session:
        # 创建根级文件夹: 技术文档
        fid_tech = gen_folder_id()
        folder_ids["技术文档"] = fid_tech
        f1 = workspace_folder_repo.create(
            session,
            folder_id=fid_tech,
            user_id=TEST_USER_ID,
            folder_name="技术文档",
            parent_folder_id=None,
            full_path="/技术文档/",
            depth=0,
            sort_order=0,
            knowledge_base_id=TEST_KB_ID_A,
            knowledge_base_name=TEST_KB_NAME_A,
            creator=TEST_CREATOR
        )
        if not f1:
            print("  ✗ 创建 '技术文档' 失败")
            return False, {}
        print(f"  ✓ 创建文件夹: /技术文档/  (id={fid_tech})")
        
        # 创建根级文件夹: 产品设计
        fid_product = gen_folder_id()
        folder_ids["产品设计"] = fid_product
        f2 = workspace_folder_repo.create(
            session,
            folder_id=fid_product,
            user_id=TEST_USER_ID,
            folder_name="产品设计",
            parent_folder_id=None,
            full_path="/产品设计/",
            depth=0,
            sort_order=1,
            knowledge_base_id=TEST_KB_ID_A,
            knowledge_base_name=TEST_KB_NAME_A,
            creator=TEST_CREATOR
        )
        if not f2:
            print("  ✗ 创建 '产品设计' 失败")
            return False, {}
        print(f"  ✓ 创建文件夹: /产品设计/  (id={fid_product})")
        
        # 创建子文件夹: 技术文档/前端
        fid_frontend = gen_folder_id()
        folder_ids["前端"] = fid_frontend
        f3 = workspace_folder_repo.create(
            session,
            folder_id=fid_frontend,
            user_id=TEST_USER_ID,
            folder_name="前端",
            parent_folder_id=fid_tech,
            full_path="/技术文档/前端/",
            depth=1,
            sort_order=0,
            knowledge_base_id=TEST_KB_ID_A,
            knowledge_base_name=TEST_KB_NAME_A,
            creator=TEST_CREATOR
        )
        if not f3:
            print("  ✗ 创建 '前端' 失败")
            return False, {}
        print(f"  ✓ 创建文件夹: /技术文档/前端/  (id={fid_frontend})")
        
        # 创建子文件夹: 技术文档/后端
        fid_backend = gen_folder_id()
        folder_ids["后端"] = fid_backend
        f4 = workspace_folder_repo.create(
            session,
            folder_id=fid_backend,
            user_id=TEST_USER_ID,
            folder_name="后端",
            parent_folder_id=fid_tech,
            full_path="/技术文档/后端/",
            depth=1,
            sort_order=1,
            knowledge_base_id=TEST_KB_ID_A,
            knowledge_base_name=TEST_KB_NAME_A,
            creator=TEST_CREATOR
        )
        if not f4:
            print("  ✗ 创建 '后端' 失败")
            return False, {}
        print(f"  ✓ 创建文件夹: /技术文档/后端/  (id={fid_backend})")
        
        # 创建孙文件夹: 技术文档/前端/React
        fid_react = gen_folder_id()
        folder_ids["React"] = fid_react
        f5 = workspace_folder_repo.create(
            session,
            folder_id=fid_react,
            user_id=TEST_USER_ID,
            folder_name="React",
            parent_folder_id=fid_frontend,
            full_path="/技术文档/前端/React/",
            depth=2,
            sort_order=0,
            knowledge_base_id=TEST_KB_ID_A,
            knowledge_base_name=TEST_KB_NAME_A,
            creator=TEST_CREATOR
        )
        if not f5:
            print("  ✗ 创建 'React' 失败")
            return False, {}
        print(f"  ✓ 创建文件夹: /技术文档/前端/React/  (id={fid_react})")
    
    # 验证: 查询所有文件夹
    with manager.get_session() as session:
        all_folders = workspace_folder_repo.get_by_user_and_knowledge_base(
            session, TEST_USER_ID, TEST_KB_ID_A
        )
        if len(all_folders) == 5:
            print(f"\n  ✓ 验证通过: 共创建 {len(all_folders)} 个文件夹")
        else:
            print(f"\n  ✗ 验证失败: 预期 5 个文件夹，实际 {len(all_folders)} 个")
            return False, {}
    
    print("\n✅ 构建文件夹结构测试通过!")
    return True, folder_ids


def test_upload_files(folder_ids: dict):
    """测试2: 上传文件到不同文件夹
    
    上传文件:
    - 根目录: README.md
    - 技术文档/: 架构设计.pdf
    - 技术文档/前端/: vue_guide.md
    - 技术文档/前端/React/: react_hooks.md, react_router.md
    - 技术文档/后端/: api_design.pdf
    - 产品设计/: PRD_v1.docx
    """
    print("\n" + "=" * 70)
    print("测试2: 上传文件到不同文件夹")
    print("=" * 70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.business import workspace_file_system_repo
    
    manager = get_mysql_manager("mysql")
    
    file_ids = {}
    
    upload_plan = [
        ("README.md", None, 1024, "text/markdown", "readme"),
        ("架构设计.pdf", folder_ids["技术文档"], 2048000, "application/pdf", "arch"),
        ("vue_guide.md", folder_ids["前端"], 5120, "text/markdown", "vue"),
        ("react_hooks.md", folder_ids["React"], 3072, "text/markdown", "hooks"),
        ("react_router.md", folder_ids["React"], 4096, "text/markdown", "router"),
        ("api_design.pdf", folder_ids["后端"], 1536000, "application/pdf", "api"),
        ("PRD_v1.docx", folder_ids["产品设计"], 512000, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "prd"),
    ]
    
    with manager.get_session() as session:
        for file_name, folder_id, size, mime, key in upload_plan:
            fid = gen_file_id()
            file_ids[key] = fid
            
            file_obj = workspace_file_system_repo.create(
                session,
                user_id=TEST_USER_ID,
                file_id=fid,
                file_name=file_name,
                folder_id=folder_id,
                file_size=size,
                mime_type=mime,
                is_text_readable=1 if mime.startswith("text/") else 0,
                knowledge_base_id=TEST_KB_ID_A,
                knowledge_base_name=TEST_KB_NAME_A,
                creator=TEST_CREATOR
            )
            
            if not file_obj:
                print(f"  ✗ 上传 '{file_name}' 失败")
                return False, {}
            
            folder_hint = "根目录" if folder_id is None else folder_id[:12]
            print(f"  ✓ 上传: {file_name} → [{folder_hint}]")
    
    # 验证: 查询用户所有文件
    with manager.get_session() as session:
        all_files = workspace_file_system_repo.get_by_user_id(session, TEST_USER_ID)
        if len(all_files) == 7:
            print(f"\n  ✓ 验证通过: 共上传 {len(all_files)} 个文件")
        else:
            print(f"\n  ✗ 验证失败: 预期 7 个文件，实际 {len(all_files)} 个")
            return False, {}
    
    print("\n✅ 上传文件测试通过!")
    return True, file_ids


def test_query_folder_tree(folder_ids: dict, file_ids: dict):
    """测试3: 查询文件夹树和文件列表"""
    print("\n" + "=" * 70)
    print("测试3: 查询文件夹树和文件列表")
    print("=" * 70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.business import (
        workspace_folder_repo, workspace_file_system_repo
    )
    
    manager = get_mysql_manager("mysql")
    
    with manager.get_session() as session:
        # 3.1 查询根目录下的文件夹
        print("\n  [3.1] 查询根目录下的文件夹:")
        root_folders = workspace_folder_repo.get_children(
            session, TEST_USER_ID, None
        )
        root_names = [f.folder_name for f in root_folders]
        print(f"    根目录文件夹: {root_names}")
        
        if len(root_folders) != 2:
            print(f"    ✗ 预期 2 个根文件夹，实际 {len(root_folders)}")
            return False
        print(f"    ✓ 根目录有 2 个文件夹")
        
        # 3.2 查询根目录下的文件
        print("\n  [3.2] 查询根目录下的文件:")
        root_files = workspace_file_system_repo.get_by_folder_id(
            session, TEST_USER_ID, None
        )
        root_file_names = [f.file_name for f in root_files]
        print(f"    根目录文件: {root_file_names}")
        
        if len(root_files) != 1 or root_files[0].file_name != "README.md":
            print(f"    ✗ 预期根目录仅有 README.md")
            return False
        print(f"    ✓ 根目录有 1 个文件")
        
        # 3.3 查询 '技术文档' 的子文件夹
        print("\n  [3.3] 查询 '技术文档' 的子文件夹:")
        tech_children = workspace_folder_repo.get_children(
            session, TEST_USER_ID, folder_ids["技术文档"]
        )
        child_names = [f.folder_name for f in tech_children]
        print(f"    技术文档的子文件夹: {child_names}")
        
        if set(child_names) != {"前端", "后端"}:
            print(f"    ✗ 预期 ['前端', '后端']")
            return False
        print(f"    ✓ 正确")
        
        # 3.4 查询 React 文件夹下的文件
        print("\n  [3.4] 查询 'React' 文件夹下的文件:")
        react_files = workspace_file_system_repo.get_by_folder_id(
            session, TEST_USER_ID, folder_ids["React"]
        )
        react_file_names = [f.file_name for f in react_files]
        print(f"    React 下的文件: {react_file_names}")
        
        if len(react_files) != 2:
            print(f"    ✗ 预期 2 个文件，实际 {len(react_files)}")
            return False
        print(f"    ✓ React 下有 2 个文件")
        
        # 3.5 查询 '技术文档' 的所有后代文件夹
        print("\n  [3.5] 查询 '技术文档' 的所有后代文件夹:")
        descendants = workspace_folder_repo.get_descendants(
            session, TEST_USER_ID, "/技术文档/"
        )
        desc_paths = [f.full_path for f in descendants]
        print(f"    后代路径: {desc_paths}")
        
        if len(descendants) != 4:
            print(f"    ✗ 预期 4 个（含自身），实际 {len(descendants)}")
            return False
        print(f"    ✓ 共 4 个文件夹（技术文档 + 前端 + 后端 + React）")
        
        # 3.6 按知识库查询文件
        print("\n  [3.6] 按知识库查询文件:")
        kb_files = workspace_file_system_repo.get_by_knowledge_base_id(
            session, TEST_USER_ID, TEST_KB_ID_A
        )
        print(f"    知识库A的文件数: {len(kb_files)}")
        
        if len(kb_files) != 7:
            print(f"    ✗ 预期 7 个文件")
            return False
        print(f"    ✓ 正确")
        
        # 3.7 打印完整的文件夹树
        print("\n  [3.7] 完整目录树:")
        all_folders = workspace_folder_repo.get_by_user_and_knowledge_base(
            session, TEST_USER_ID, TEST_KB_ID_A
        )
        all_files = workspace_file_system_repo.get_by_knowledge_base_id(
            session, TEST_USER_ID, TEST_KB_ID_A
        )
        print_folder_tree(all_folders, all_files)
    
    print("\n✅ 查询文件夹树测试通过!")
    return True


def test_move_file(folder_ids: dict, file_ids: dict):
    """测试4: 移动文件
    
    操作: 将 vue_guide.md 从 '前端' 文件夹移动到 '后端' 文件夹
    """
    print("\n" + "=" * 70)
    print("测试4: 移动文件（vue_guide.md: 前端 → 后端）")
    print("=" * 70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.business import workspace_file_system_repo
    
    manager = get_mysql_manager("mysql")
    
    vue_file_id = file_ids["vue"]
    target_folder_id = folder_ids["后端"]
    
    with manager.get_session() as session:
        # 查询移动前的状态
        file_obj = workspace_file_system_repo.get_by_user_and_file(
            session, TEST_USER_ID, vue_file_id
        )
        if not file_obj:
            print("  ✗ 未找到 vue_guide.md")
            return False
        
        print(f"  移动前 folder_id: {file_obj.folder_id}")
        
        # 执行移动: 只需修改 folder_id
        file_obj.folder_id = target_folder_id
        file_obj.updater = TEST_CREATOR
        session.commit()
        session.refresh(file_obj)
        
        print(f"  移动后 folder_id: {file_obj.folder_id}")
        
        if file_obj.folder_id != target_folder_id:
            print("  ✗ 移动失败")
            return False
        print("  ✓ 文件移动成功")
    
    # 验证: 前端文件夹应无文件，后端文件夹应有 2 个文件
    with manager.get_session() as session:
        frontend_files = workspace_file_system_repo.get_by_folder_id(
            session, TEST_USER_ID, folder_ids["前端"]
        )
        backend_files = workspace_file_system_repo.get_by_folder_id(
            session, TEST_USER_ID, folder_ids["后端"]
        )
        
        print(f"\n  验证 - 前端文件夹文件数: {len(frontend_files)} (预期: 0)")
        print(f"  验证 - 后端文件夹文件数: {len(backend_files)} (预期: 2)")
        
        if len(frontend_files) != 0:
            print("  ✗ 前端文件夹仍有文件")
            return False
        if len(backend_files) != 2:
            print("  ✗ 后端文件夹文件数量不对")
            return False
        
        backend_names = sorted([f.file_name for f in backend_files])
        print(f"  验证 - 后端文件夹包含: {backend_names}")
    
    print("\n✅ 文件移动测试通过!")
    return True


def test_rename_folder(folder_ids: dict):
    """测试5: 文件夹重命名
    
    操作: 将 '前端' 重命名为 '前端开发'
    需要同步更新该文件夹和所有后代的 full_path
    """
    print("\n" + "=" * 70)
    print("测试5: 文件夹重命名（前端 → 前端开发）")
    print("=" * 70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.business import workspace_folder_repo
    
    manager = get_mysql_manager("mysql")
    
    frontend_id = folder_ids["前端"]
    old_path = "/技术文档/前端/"
    new_path = "/技术文档/前端开发/"
    
    with manager.get_session() as session:
        # 获取该文件夹及其所有后代
        descendants = workspace_folder_repo.get_descendants(
            session, TEST_USER_ID, old_path
        )
        print(f"  受影响的文件夹数: {len(descendants)}")
        
        for folder in descendants:
            old_full_path = folder.full_path
            new_full_path = old_full_path.replace(old_path, new_path, 1)
            folder.full_path = new_full_path
            folder.updater = TEST_CREATOR
            print(f"    路径更新: {old_full_path} → {new_full_path}")
        
        # 更新文件夹名称
        frontend_folder = workspace_folder_repo.get_by_id(session, frontend_id)
        if frontend_folder:
            frontend_folder.folder_name = "前端开发"
            frontend_folder.updater = TEST_CREATOR
        
        session.commit()
    
    # 验证: 检查路径是否正确更新
    with manager.get_session() as session:
        # 旧路径应找不到
        old_result = workspace_folder_repo.get_by_full_path(
            session, TEST_USER_ID, old_path
        )
        if old_result is not None:
            print("  ✗ 旧路径仍然存在")
            return False
        print("  ✓ 旧路径已不存在")
        
        # 新路径应找到
        new_result = workspace_folder_repo.get_by_full_path(
            session, TEST_USER_ID, new_path
        )
        if new_result is None:
            print("  ✗ 新路径未找到")
            return False
        print(f"  ✓ 新路径存在: {new_result.folder_name} ({new_result.full_path})")
        
        # React 子文件夹路径也应更新
        react_folder = workspace_folder_repo.get_by_id(session, folder_ids["React"])
        expected_react_path = "/技术文档/前端开发/React/"
        if react_folder and react_folder.full_path == expected_react_path:
            print(f"  ✓ 子文件夹路径同步更新: {react_folder.full_path}")
        else:
            actual = react_folder.full_path if react_folder else "None"
            print(f"  ✗ 子文件夹路径未同步: {actual}, 预期: {expected_react_path}")
            return False
    
    print("\n✅ 文件夹重命名测试通过!")
    return True


def test_move_folder(folder_ids: dict):
    """测试6: 移动文件夹
    
    操作: 将 'React' 文件夹从 '前端开发' 下移动到 '技术文档' 根下
    
    移动前: /技术文档/前端开发/React/  (depth=2)
    移动后: /技术文档/React/          (depth=1)
    """
    print("\n" + "=" * 70)
    print("测试6: 移动文件夹（React: 前端开发 → 技术文档根下）")
    print("=" * 70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.business import workspace_folder_repo
    
    manager = get_mysql_manager("mysql")
    
    react_id = folder_ids["React"]
    tech_id = folder_ids["技术文档"]
    old_path = "/技术文档/前端开发/React/"
    new_path = "/技术文档/React/"
    
    with manager.get_session() as session:
        # 获取 React 及其所有后代（这里 React 没有子文件夹，仅自身）
        descendants = workspace_folder_repo.get_descendants(
            session, TEST_USER_ID, old_path
        )
        print(f"  受影响的文件夹数: {len(descendants)}")
        
        # 计算 depth 差值
        old_depth = 2
        new_depth = 1
        depth_diff = new_depth - old_depth
        
        for folder in descendants:
            old_full_path = folder.full_path
            new_full_path = old_full_path.replace(old_path, new_path, 1)
            folder.full_path = new_full_path
            folder.depth = folder.depth + depth_diff
            folder.updater = TEST_CREATOR
            print(f"    {old_full_path} → {new_full_path} (depth: {folder.depth - depth_diff} → {folder.depth})")
        
        # 更新 parent_folder_id
        react_folder = workspace_folder_repo.get_by_id(session, react_id)
        if react_folder:
            react_folder.parent_folder_id = tech_id
            react_folder.updater = TEST_CREATOR
        
        session.commit()
    
    # 验证
    with manager.get_session() as session:
        react_folder = workspace_folder_repo.get_by_id(session, react_id)
        
        if not react_folder:
            print("  ✗ React 文件夹不存在")
            return False
        
        if react_folder.parent_folder_id != tech_id:
            print(f"  ✗ parent_folder_id 不正确: {react_folder.parent_folder_id}")
            return False
        print(f"  ✓ parent_folder_id 正确: {react_folder.parent_folder_id}")
        
        if react_folder.full_path != new_path:
            print(f"  ✗ full_path 不正确: {react_folder.full_path}")
            return False
        print(f"  ✓ full_path 正确: {react_folder.full_path}")
        
        if react_folder.depth != 1:
            print(f"  ✗ depth 不正确: {react_folder.depth}")
            return False
        print(f"  ✓ depth 正确: {react_folder.depth}")
        
        # 验证 '技术文档' 现在有 3 个子文件夹
        tech_children = workspace_folder_repo.get_children(
            session, TEST_USER_ID, tech_id
        )
        child_names = sorted([f.folder_name for f in tech_children])
        print(f"  ✓ 技术文档的子文件夹: {child_names} (预期: 3 个)")
        
        if len(tech_children) != 3:
            print(f"  ✗ 预期 3 个子文件夹，实际 {len(tech_children)}")
            return False
    
    print("\n✅ 文件夹移动测试通过!")
    return True


def test_cascade_delete_folder(folder_ids: dict, file_ids: dict):
    """测试7: 级联删除文件夹
    
    操作: 删除 '技术文档' 文件夹
    预期: 技术文档 及其所有子文件夹（前端开发、后端、React）被软删除
          这些文件夹下的所有文件也被软删除
    """
    print("\n" + "=" * 70)
    print("测试7: 级联删除文件夹（删除 '技术文档' 及所有内容）")
    print("=" * 70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.business import (
        workspace_folder_repo, workspace_file_system_repo
    )
    
    manager = get_mysql_manager("mysql")
    
    tech_id = folder_ids["技术文档"]
    tech_path = "/技术文档/"
    
    with manager.get_session() as session:
        # 先统计受影响的数据
        desc_folders = workspace_folder_repo.get_descendants(
            session, TEST_USER_ID, tech_path
        )
        print(f"  即将删除的文件夹数: {len(desc_folders)}")
        for f in desc_folders:
            print(f"    - {f.full_path}")
        
        # 收集所有受影响的 folder_id
        affected_folder_ids = [f.folder_id for f in desc_folders]
        
        # 统计这些文件夹中的文件
        total_files = 0
        for fid in affected_folder_ids:
            folder_files = workspace_file_system_repo.get_by_folder_id(
                session, TEST_USER_ID, fid
            )
            total_files += len(folder_files)
            for ff in folder_files:
                print(f"    - [文件] {ff.file_name} (in {fid[:12]})")
        
        print(f"  即将删除的文件数: {total_files}")
    
    # 执行级联删除
    with manager.get_session() as session:
        # 步骤1: 软删除所有后代文件夹（含自身）
        success = workspace_folder_repo.soft_delete_with_descendants(
            session, TEST_USER_ID, tech_id, tech_path, updater=TEST_CREATOR
        )
        if not success:
            print("  ✗ 文件夹级联删除失败")
            return False
        print("  ✓ 文件夹级联软删除完成")
    
    with manager.get_session() as session:
        # 步骤2: 软删除这些文件夹下的所有文件
        for fid in affected_folder_ids:
            workspace_file_system_repo.delete_by_folder_id(
                session, TEST_USER_ID, fid, updater=TEST_CREATOR
            )
        print("  ✓ 文件级联软删除完成")
    
    # 验证
    with manager.get_session() as session:
        # 技术文档文件夹应查不到
        remaining_folders = workspace_folder_repo.get_descendants(
            session, TEST_USER_ID, tech_path
        )
        if len(remaining_folders) != 0:
            print(f"  ✗ 仍有 {len(remaining_folders)} 个文件夹未删除")
            return False
        print("  ✓ 验证: 所有技术文档文件夹已删除")
        
        # 这些文件夹下的文件也应查不到
        for fid in affected_folder_ids:
            remaining_files = workspace_file_system_repo.get_by_folder_id(
                session, TEST_USER_ID, fid
            )
            if len(remaining_files) != 0:
                print(f"  ✗ 文件夹 {fid} 下仍有 {len(remaining_files)} 个文件")
                return False
        print("  ✓ 验证: 所有相关文件已删除")
        
        # 产品设计文件夹应仍然存在
        product_folder = workspace_folder_repo.get_by_id(
            session, folder_ids["产品设计"]
        )
        if not product_folder:
            print("  ✗ '产品设计' 文件夹不应被删除")
            return False
        print(f"  ✓ 验证: '产品设计' 文件夹未受影响")
        
        # 根目录的 README.md 应仍然存在
        root_files = workspace_file_system_repo.get_by_folder_id(
            session, TEST_USER_ID, None
        )
        if len(root_files) != 1:
            print("  ✗ 根目录文件不应被删除")
            return False
        print(f"  ✓ 验证: 根目录 README.md 未受影响")
    
    print("\n✅ 级联删除文件夹测试通过!")
    return True


def test_multi_knowledge_base(folder_ids: dict):
    """测试8: 多知识库隔离验证
    
    操作:
    - 在知识库B中创建文件夹和文件
    - 验证知识库A和B的数据完全隔离
    """
    print("\n" + "=" * 70)
    print("测试8: 多知识库隔离验证")
    print("=" * 70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.business import (
        workspace_folder_repo, workspace_file_system_repo
    )
    
    manager = get_mysql_manager("mysql")
    
    # 在知识库B中创建一个文件夹和一个文件
    kb_b_folder_id = gen_folder_id()
    kb_b_file_id = gen_file_id()
    
    with manager.get_session() as session:
        folder = workspace_folder_repo.create(
            session,
            folder_id=kb_b_folder_id,
            user_id=TEST_USER_ID,
            folder_name="研发资料",
            parent_folder_id=None,
            full_path="/研发资料/",
            depth=0,
            sort_order=0,
            knowledge_base_id=TEST_KB_ID_B,
            knowledge_base_name=TEST_KB_NAME_B,
            creator=TEST_CREATOR
        )
        if not folder:
            print("  ✗ 创建知识库B文件夹失败")
            return False
        print(f"  ✓ 在知识库B创建文件夹: /研发资料/")
        
        file_obj = workspace_file_system_repo.create(
            session,
            user_id=TEST_USER_ID,
            file_id=kb_b_file_id,
            file_name="研发规范.pdf",
            folder_id=kb_b_folder_id,
            file_size=1024,
            mime_type="application/pdf",
            knowledge_base_id=TEST_KB_ID_B,
            knowledge_base_name=TEST_KB_NAME_B,
            creator=TEST_CREATOR
        )
        if not file_obj:
            print("  ✗ 在知识库B上传文件失败")
            return False
        print(f"  ✓ 在知识库B上传文件: 研发规范.pdf")
    
    # 验证隔离
    with manager.get_session() as session:
        # 知识库A的文件夹（产品设计仍在，技术文档已删除）
        kb_a_folders = workspace_folder_repo.get_by_user_and_knowledge_base(
            session, TEST_USER_ID, TEST_KB_ID_A
        )
        kb_a_folder_names = [f.folder_name for f in kb_a_folders]
        print(f"\n  知识库A的文件夹: {kb_a_folder_names}")
        
        # 知识库B的文件夹
        kb_b_folders = workspace_folder_repo.get_by_user_and_knowledge_base(
            session, TEST_USER_ID, TEST_KB_ID_B
        )
        kb_b_folder_names = [f.folder_name for f in kb_b_folders]
        print(f"  知识库B的文件夹: {kb_b_folder_names}")
        
        if "研发资料" in kb_a_folder_names:
            print("  ✗ 知识库A不应包含知识库B的文件夹")
            return False
        
        if "产品设计" in kb_b_folder_names:
            print("  ✗ 知识库B不应包含知识库A的文件夹")
            return False
        
        print("  ✓ 文件夹隔离正确")
        
        # 知识库A的文件
        kb_a_files = workspace_file_system_repo.get_by_knowledge_base_id(
            session, TEST_USER_ID, TEST_KB_ID_A
        )
        kb_a_file_names = [f.file_name for f in kb_a_files]
        print(f"\n  知识库A的文件: {kb_a_file_names}")
        
        # 知识库B的文件
        kb_b_files = workspace_file_system_repo.get_by_knowledge_base_id(
            session, TEST_USER_ID, TEST_KB_ID_B
        )
        kb_b_file_names = [f.file_name for f in kb_b_files]
        print(f"  知识库B的文件: {kb_b_file_names}")
        
        if "研发规范.pdf" in kb_a_file_names:
            print("  ✗ 知识库A不应包含知识库B的文件")
            return False
        
        if len(kb_b_files) != 1 or kb_b_files[0].file_name != "研发规范.pdf":
            print("  ✗ 知识库B的文件不正确")
            return False
        
        print("  ✓ 文件隔离正确")
    
    print("\n✅ 多知识库隔离验证通过!")
    return True


def test_final_state_verification(folder_ids: dict):
    """测试9: 最终状态全量验证
    
    经过测试1~8的所有操作后，预期最终状态：
    
    知识库A:
    / (根目录)
    ├── README.md
    └── 产品设计/              ← 唯一存活的文件夹
        └── PRD_v1.docx
    
    知识库B:
    / (根目录)
    └── 研发资料/
        └── 研发规范.pdf
    
    总计: 2 个文件夹, 3 个文件
    已删除: 4 个文件夹 (技术文档、前端开发、后端、React), 5 个文件
    """
    print("\n" + "=" * 70)
    print("测试9: 最终状态全量验证")
    print("=" * 70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.business import (
        workspace_folder_repo, workspace_file_system_repo
    )
    
    manager = get_mysql_manager("mysql")
    all_pass = True
    
    with manager.get_session() as session:
        # ========== 知识库A验证 ==========
        print("\n  [知识库A] 验证文件夹:")
        
        kb_a_folders = workspace_folder_repo.get_by_user_and_knowledge_base(
            session, TEST_USER_ID, TEST_KB_ID_A
        )
        kb_a_folder_names = [f.folder_name for f in kb_a_folders]
        
        if len(kb_a_folders) != 1:
            print(f"    ✗ 文件夹数量: {len(kb_a_folders)}, 预期: 1")
            all_pass = False
        elif kb_a_folder_names != ["产品设计"]:
            print(f"    ✗ 文件夹名称: {kb_a_folder_names}, 预期: ['产品设计']")
            all_pass = False
        else:
            print(f"    ✓ 文件夹: {kb_a_folder_names}")
        
        # 验证知识库A的文件
        print("\n  [知识库A] 验证文件:")
        
        kb_a_files = workspace_file_system_repo.get_by_knowledge_base_id(
            session, TEST_USER_ID, TEST_KB_ID_A
        )
        kb_a_file_names = sorted([f.file_name for f in kb_a_files])
        expected_a_files = sorted(["README.md", "PRD_v1.docx"])
        
        if kb_a_file_names != expected_a_files:
            print(f"    ✗ 文件列表: {kb_a_file_names}, 预期: {expected_a_files}")
            all_pass = False
        else:
            print(f"    ✓ 文件: {kb_a_file_names}")
        
        # 验证 README.md 在根目录
        root_files = workspace_file_system_repo.get_by_folder_id(
            session, TEST_USER_ID, None
        )
        root_file_names = [f.file_name for f in root_files]
        
        if "README.md" not in root_file_names:
            print(f"    ✗ README.md 应在根目录, 实际根目录文件: {root_file_names}")
            all_pass = False
        else:
            print(f"    ✓ README.md 在根目录")
        
        # 验证 PRD_v1.docx 在产品设计下
        product_files = workspace_file_system_repo.get_by_folder_id(
            session, TEST_USER_ID, folder_ids["产品设计"]
        )
        product_file_names = [f.file_name for f in product_files]
        
        if product_file_names != ["PRD_v1.docx"]:
            print(f"    ✗ 产品设计下: {product_file_names}, 预期: ['PRD_v1.docx']")
            all_pass = False
        else:
            print(f"    ✓ PRD_v1.docx 在 /产品设计/ 下")
        
        # ========== 知识库B验证 ==========
        print("\n  [知识库B] 验证文件夹:")
        
        kb_b_folders = workspace_folder_repo.get_by_user_and_knowledge_base(
            session, TEST_USER_ID, TEST_KB_ID_B
        )
        kb_b_folder_names = [f.folder_name for f in kb_b_folders]
        
        if len(kb_b_folders) != 1 or kb_b_folder_names != ["研发资料"]:
            print(f"    ✗ 文件夹: {kb_b_folder_names}, 预期: ['研发资料']")
            all_pass = False
        else:
            print(f"    ✓ 文件夹: {kb_b_folder_names}")
        
        print("\n  [知识库B] 验证文件:")
        
        kb_b_files = workspace_file_system_repo.get_by_knowledge_base_id(
            session, TEST_USER_ID, TEST_KB_ID_B
        )
        kb_b_file_names = [f.file_name for f in kb_b_files]
        
        if kb_b_file_names != ["研发规范.pdf"]:
            print(f"    ✗ 文件: {kb_b_file_names}, 预期: ['研发规范.pdf']")
            all_pass = False
        else:
            print(f"    ✓ 文件: {kb_b_file_names}")
        
        # ========== 全量明细表（cleanup 前的真实数据库状态） ==========
        print("\n  [数据库全量明细] 所有文件夹记录（含 deleted 状态）:")
        
        from src.db.mysql.models.business import WorkspaceFolder, WorkspaceFileSystem
        
        all_folder_records = session.query(WorkspaceFolder).filter(
            WorkspaceFolder.user_id == TEST_USER_ID,
            WorkspaceFolder.creator == TEST_CREATOR
        ).order_by(WorkspaceFolder.knowledge_base_id, WorkspaceFolder.full_path).all()
        
        print(f"    {'文件夹名':<12} {'full_path':<30} {'KB':<12} {'deleted':<8} {'状态'}")
        print(f"    {'-'*12} {'-'*30} {'-'*12} {'-'*8} {'-'*6}")
        for f in all_folder_records:
            status_label = "已删除" if f.deleted == 1 else "存活"
            print(
                f"    {f.folder_name:<12} {f.full_path:<30} "
                f"{(f.knowledge_base_id or ''):<12} {f.deleted:<8} {status_label}"
            )
        
        print(f"\n  [数据库全量明细] 所有文件记录（含 deleted 状态）:")
        
        all_file_records = session.query(WorkspaceFileSystem).filter(
            WorkspaceFileSystem.user_id == TEST_USER_ID,
            WorkspaceFileSystem.creator == TEST_CREATOR
        ).order_by(WorkspaceFileSystem.knowledge_base_id, WorkspaceFileSystem.file_name).all()
        
        print(f"    {'文件名':<20} {'folder_id':<16} {'KB':<12} {'deleted':<8} {'状态'}")
        print(f"    {'-'*20} {'-'*16} {'-'*12} {'-'*8} {'-'*6}")
        for f in all_file_records:
            status_label = "已删除" if f.deleted == 1 else "存活"
            fid_display = (f.folder_id or "(根目录)")[:16]
            print(
                f"    {f.file_name:<20} {fid_display:<16} "
                f"{(f.knowledge_base_id or ''):<12} {f.deleted:<8} {status_label}"
            )
        
        # ========== 已删除数据验证 ==========
        print("\n  [已删除数据] 验证软删除记录:")
        
        alive_folder_records = [f for f in all_folder_records if f.deleted == 0]
        deleted_folder_records = [f for f in all_folder_records if f.deleted == 1]
        alive_file_records = [f for f in all_file_records if f.deleted == 0]
        deleted_file_records = [f for f in all_file_records if f.deleted == 1]
        
        deleted_folder_names = sorted([f.folder_name for f in deleted_folder_records])
        expected_deleted_folders = sorted(["技术文档", "前端开发", "后端", "React"])
        
        if deleted_folder_names != expected_deleted_folders:
            print(f"    ✗ 已删除文件夹: {deleted_folder_names}, 预期: {expected_deleted_folders}")
            all_pass = False
        else:
            print(f"    ✓ 已删除文件夹 ({len(deleted_folder_records)} 个): {deleted_folder_names}")
        
        deleted_file_names = sorted([f.file_name for f in deleted_file_records])
        expected_deleted_files = sorted([
            "架构设计.pdf", "vue_guide.md", "react_hooks.md",
            "react_router.md", "api_design.pdf"
        ])
        
        if deleted_file_names != expected_deleted_files:
            print(f"    ✗ 已删除文件: {deleted_file_names}, 预期: {expected_deleted_files}")
            all_pass = False
        else:
            print(f"    ✓ 已删除文件 ({len(deleted_file_records)} 个): {deleted_file_names}")
        
        # 验证存活记录
        alive_folder_names = sorted([f.folder_name for f in alive_folder_records])
        expected_alive_folders = sorted(["产品设计", "研发资料"])
        
        if alive_folder_names != expected_alive_folders:
            print(f"    ✗ 存活文件夹: {alive_folder_names}, 预期: {expected_alive_folders}")
            all_pass = False
        else:
            print(f"    ✓ 存活文件夹 ({len(alive_folder_records)} 个): {alive_folder_names}")
        
        alive_file_names = sorted([f.file_name for f in alive_file_records])
        expected_alive_files = sorted(["README.md", "PRD_v1.docx", "研发规范.pdf"])
        
        if alive_file_names != expected_alive_files:
            print(f"    ✗ 存活文件: {alive_file_names}, 预期: {expected_alive_files}")
            all_pass = False
        else:
            print(f"    ✓ 存活文件 ({len(alive_file_records)} 个): {alive_file_names}")
        
        # ========== 总量验证 ==========
        print("\n  [总量统计]:")
        
        print(f"    存活文件夹: {len(alive_folder_records)} 个 (预期: 2)")
        print(f"    存活文件:   {len(alive_file_records)} 个 (预期: 3)")
        print(f"    已删除文件夹: {len(deleted_folder_records)} 个 (预期: 4)")
        print(f"    已删除文件:   {len(deleted_file_records)} 个 (预期: 5)")
        
        if len(alive_folder_records) != 2 or len(alive_file_records) != 3:
            all_pass = False
        if len(deleted_folder_records) != 4 or len(deleted_file_records) != 5:
            all_pass = False
        
        # ========== 打印最终目录树（仅存活数据） ==========
        print("\n  [最终目录树] (仅 deleted=0 的记录):")
        print("    知识库A:")
        print_folder_tree(kb_a_folders, kb_a_files, "  ")
        print("    知识库B:")
        print_folder_tree(kb_b_folders, kb_b_files, "  ")
    
    if all_pass:
        print("\n✅ 最终状态全量验证通过!")
    else:
        print("\n✗ 最终状态验证失败!")
    
    return all_pass


# ==================== 数据清理 ====================


def purge_test_data():
    """物理删除所有测试数据（测试前调用，清除上次残留）"""
    try:
        from src.db.mysql.connection.factory import get_mysql_manager
        from src.db.mysql.models.business import WorkspaceFolder, WorkspaceFileSystem
        
        manager = get_mysql_manager("mysql")
        
        with manager.get_session() as session:
            file_count = session.query(WorkspaceFileSystem).filter(
                WorkspaceFileSystem.creator == TEST_CREATOR
            ).delete(synchronize_session='fetch')
            
            folder_count = session.query(WorkspaceFolder).filter(
                WorkspaceFolder.creator == TEST_CREATOR
            ).delete(synchronize_session='fetch')
            
            session.commit()
        
        total = folder_count + file_count
        if total > 0:
            print(f"🧹 测试前清理: 物理删除 {total} 条残留数据（文件夹: {folder_count}, 文件: {file_count}）")
        else:
            print(f"✓ 数据库干净，无残留测试数据")
            
    except Exception as e:
        print(f"⚠️  测试前清理出错: {e}")
        import traceback
        traceback.print_exc()


def cleanup_all_test_data():
    """清理所有测试数据（测试后调用，物理删除）"""
    try:
        from src.db.mysql.connection.factory import get_mysql_manager
        from src.db.mysql.models.business import WorkspaceFolder, WorkspaceFileSystem
        
        manager = get_mysql_manager("mysql")
        
        with manager.get_session() as session:
            file_count = session.query(WorkspaceFileSystem).filter(
                WorkspaceFileSystem.creator == TEST_CREATOR
            ).delete(synchronize_session='fetch')
            
            folder_count = session.query(WorkspaceFolder).filter(
                WorkspaceFolder.creator == TEST_CREATOR
            ).delete(synchronize_session='fetch')
            
            session.commit()
        
        total = folder_count + file_count
        if total > 0:
            print(f"\n🧹 测试后清理: 物理删除 {total} 条测试数据（文件夹: {folder_count}, 文件: {file_count}）")
        else:
            print(f"\n✓ 数据库中没有需要清理的测试数据")
            
    except Exception as e:
        print(f"\n⚠️  清理数据时出错: {e}")
        import traceback
        traceback.print_exc()


# ==================== 主入口 ====================


def run_all_tests(cleanup_after: bool = False):
    """运行所有测试
    
    Args:
        cleanup_after: 测试完成后是否物理删除所有测试数据，默认不清理
    """
    print("\n" + "=" * 70)
    print("WorkspaceFolder + WorkspaceFileSystem 文件夹管理测试套件")
    print("=" * 70)
    print(f"项目根目录: {project_root}")
    print(f"测试用户: {TEST_USER_ID}")
    print(f"知识库A: {TEST_KB_ID_A} ({TEST_KB_NAME_A})")
    print(f"知识库B: {TEST_KB_ID_B} ({TEST_KB_NAME_B})")
    
    if cleanup_after:
        print(f"🧹 数据清理模式: 测试后将物理删除数据（--cleanup）")
    else:
        print(f"💾 数据保留模式: 测试后保留数据供检查（加 --cleanup 可清理）")
    
    # 测试前清理上次残留数据
    purge_test_data()
    
    results = []
    folder_ids = {}
    file_ids = {}
    
    # 测试1: 构建文件夹结构
    try:
        success, folder_ids = test_build_folder_structure()
        results.append(("构建文件夹结构", success))
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("构建文件夹结构", False))
    
    if not folder_ids:
        print("\n⚠️  文件夹创建失败，跳过后续测试")
        return 1
    
    # 测试2: 上传文件
    try:
        success, file_ids = test_upload_files(folder_ids)
        results.append(("上传文件到文件夹", success))
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("上传文件到文件夹", False))
    
    if not file_ids:
        print("\n⚠️  文件上传失败，跳过后续测试")
        return 1
    
    # 测试3: 查询文件夹树
    try:
        success = test_query_folder_tree(folder_ids, file_ids)
        results.append(("查询文件夹树和文件", success))
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("查询文件夹树和文件", False))
    
    # 测试4: 移动文件
    try:
        success = test_move_file(folder_ids, file_ids)
        results.append(("移动文件", success))
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("移动文件", False))
    
    # 测试5: 文件夹重命名
    try:
        success = test_rename_folder(folder_ids)
        results.append(("文件夹重命名", success))
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("文件夹重命名", False))
    
    # 测试6: 移动文件夹
    try:
        success = test_move_folder(folder_ids)
        results.append(("移动文件夹", success))
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("移动文件夹", False))
    
    # 测试7: 级联删除文件夹
    try:
        success = test_cascade_delete_folder(folder_ids, file_ids)
        results.append(("级联删除文件夹", success))
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("级联删除文件夹", False))
    
    # 测试8: 多知识库隔离
    try:
        success = test_multi_knowledge_base(folder_ids)
        results.append(("多知识库隔离", success))
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("多知识库隔离", False))
    
    # 测试9: 最终状态全量验证
    try:
        success = test_final_state_verification(folder_ids)
        results.append(("最终状态全量验证", success))
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("最终状态全量验证", False))
    
    # 显示测试结果汇总
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    # 测试后清理（仅在 --cleanup 参数时执行）
    if cleanup_after:
        try:
            cleanup_all_test_data()
        except Exception as e:
            print(f"\n⚠️  清理数据时出错: {e}")
    else:
        print(f"\n💾 测试数据已保留，可在数据库中查看")
        print(f"   - SELECT * FROM workspace_folder WHERE creator = '{TEST_CREATOR}';")
        print(f"   - SELECT * FROM workspace_file_system WHERE creator = '{TEST_CREATOR}';")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="文件夹管理测试套件")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="测试完成后物理删除所有测试数据（默认不清理）"
    )
    args = parser.parse_args()
    
    exit_code = run_all_tests(cleanup_after=args.cleanup)
    sys.exit(exit_code)
