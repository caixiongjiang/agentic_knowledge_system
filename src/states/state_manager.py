#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : state_manager.py
@Author  : caixiongjiang
@Date    : 2025/12/30 15:33
@Function: 
    状态管理器 - 负责状态的持久化存储和管理
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from .states import (
    DocumentState,
    BatchProcessState,
    ProcessStage,
    ProcessStatus,
    ExtractResult,
    ParserResult,
    SplitterResult,
    UpdateResult
)


class StateManager:
    """状态管理器
    
    负责文档处理状态的持久化、加载和更新操作
    支持单文档和批量文档的状态管理
    """
    
    def __init__(self, storage_dir: str = "tmp_results/states"):
        """初始化状态管理器
        
        Args:
            storage_dir: 状态文件存储目录
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 为不同类型的状态创建子目录
        self.doc_states_dir = self.storage_dir / "documents"
        self.batch_states_dir = self.storage_dir / "batches"
        self.doc_states_dir.mkdir(parents=True, exist_ok=True)
        self.batch_states_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"StateManager initialized with storage_dir: {self.storage_dir}")
    
    # ============ 文档状态管理 ============
    
    def create_document_state(
        self,
        file_path: str,
        file_name: Optional[str] = None,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DocumentState:
        """创建新的文档状态
        
        Args:
            file_path: 文件路径
            file_name: 文件名（可选，从 file_path 推断）
            doc_id: 文档ID（可选，自动生成）
            metadata: 额外的元数据
        
        Returns:
            DocumentState: 新创建的文档状态
        """
        file_path_obj = Path(file_path)
        
        # 自动生成文档ID
        if doc_id is None:
            doc_id = self._generate_doc_id()
        
        # 自动推断文件名
        if file_name is None:
            file_name = file_path_obj.name
        
        # 获取文件信息
        file_size = file_path_obj.stat().st_size if file_path_obj.exists() else 0
        file_type = file_path_obj.suffix.lstrip('.')
        
        # 创建文档状态
        doc_state = DocumentState(
            doc_id=doc_id,
            file_name=file_name,
            file_path=str(file_path),
            file_type=file_type,
            file_size=file_size,
            metadata=metadata or {}
        )
        
        # 保存状态
        self.save_document_state(doc_state)
        
        logger.info(f"Created document state: {doc_id} for file: {file_name}")
        return doc_state
    
    def save_document_state(self, state: DocumentState) -> None:
        """保存文档状态到文件
        
        Args:
            state: 文档状态对象
        """
        state.updated_at = datetime.now()
        file_path = self.doc_states_dir / f"{state.doc_id}.json"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(
                    state.model_dump(mode='json'),
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=str
                )
            logger.debug(f"Saved document state: {state.doc_id}")
        except Exception as e:
            logger.error(f"Failed to save document state {state.doc_id}: {e}")
            raise
    
    def load_document_state(self, doc_id: str) -> Optional[DocumentState]:
        """从文件加载文档状态
        
        Args:
            doc_id: 文档ID
        
        Returns:
            Optional[DocumentState]: 文档状态对象，如果不存在则返回 None
        """
        file_path = self.doc_states_dir / f"{doc_id}.json"
        
        if not file_path.exists():
            logger.warning(f"Document state not found: {doc_id}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 将 datetime 字符串转换回 datetime 对象
            for field in ['created_at', 'updated_at', 'started_at', 'completed_at']:
                if data.get(field):
                    data[field] = datetime.fromisoformat(data[field])
            
            state = DocumentState(**data)
            logger.debug(f"Loaded document state: {doc_id}")
            return state
        except Exception as e:
            logger.error(f"Failed to load document state {doc_id}: {e}")
            raise
    
    def delete_document_state(self, doc_id: str) -> bool:
        """删除文档状态文件
        
        Args:
            doc_id: 文档ID
        
        Returns:
            bool: 是否成功删除
        """
        file_path = self.doc_states_dir / f"{doc_id}.json"
        
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted document state: {doc_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete document state {doc_id}: {e}")
                return False
        else:
            logger.warning(f"Document state not found for deletion: {doc_id}")
            return False
    
    def list_document_states(
        self, 
        status: Optional[ProcessStatus] = None,
        stage: Optional[ProcessStage] = None
    ) -> List[DocumentState]:
        """列出所有文档状态
        
        Args:
            status: 过滤特定状态（可选）
            stage: 过滤特定阶段（可选）
        
        Returns:
            List[DocumentState]: 文档状态列表
        """
        states = []
        
        for file_path in self.doc_states_dir.glob("*.json"):
            try:
                state = self.load_document_state(file_path.stem)
                if state:
                    # 应用过滤条件
                    if status and state.overall_status != status:
                        continue
                    if stage and state.current_stage != stage:
                        continue
                    states.append(state)
            except Exception as e:
                logger.error(f"Failed to load state from {file_path}: {e}")
        
        return states
    
    # ============ 阶段更新方法 ============
    
    def start_processing(self, doc_id: str) -> None:
        """标记文档开始处理
        
        Args:
            doc_id: 文档ID
        """
        state = self.load_document_state(doc_id)
        if state is None:
            raise ValueError(f"Document state not found: {doc_id}")
        
        state.overall_status = ProcessStatus.PROCESSING
        state.started_at = datetime.now()
        self.save_document_state(state)
        logger.info(f"Started processing document: {doc_id}")
    
    def update_extract_result(
        self, 
        doc_id: str, 
        result: ExtractResult
    ) -> None:
        """更新提取阶段结果
        
        Args:
            doc_id: 文档ID
            result: 提取结果
        """
        state = self.load_document_state(doc_id)
        if state is None:
            raise ValueError(f"Document state not found: {doc_id}")
        
        state.extract_result = result
        state.current_stage = ProcessStage.PARSER
        
        if result.status == ProcessStatus.FAILED:
            state.overall_status = ProcessStatus.FAILED
            state.add_error(ProcessStage.EXTRACT, result.error_message or "Unknown error")
        
        self.save_document_state(state)
        logger.info(f"Updated extract result for document: {doc_id}, status: {result.status}")
    
    def update_parser_result(
        self,
        doc_id: str,
        result: ParserResult
    ) -> None:
        """更新解析阶段结果
        
        Args:
            doc_id: 文档ID
            result: 解析结果
        """
        state = self.load_document_state(doc_id)
        if state is None:
            raise ValueError(f"Document state not found: {doc_id}")
        
        state.parser_result = result
        state.current_stage = ProcessStage.SPLITTER
        
        if result.status == ProcessStatus.FAILED:
            state.overall_status = ProcessStatus.FAILED
            state.add_error(ProcessStage.PARSER, result.error_message or "Unknown error")
        
        self.save_document_state(state)
        logger.info(f"Updated parser result for document: {doc_id}, status: {result.status}")
    
    def update_splitter_result(
        self,
        doc_id: str,
        result: SplitterResult
    ) -> None:
        """更新分割阶段结果
        
        Args:
            doc_id: 文档ID
            result: 分割结果
        """
        state = self.load_document_state(doc_id)
        if state is None:
            raise ValueError(f"Document state not found: {doc_id}")
        
        state.splitter_result = result
        state.current_stage = ProcessStage.UPDATE
        
        if result.status == ProcessStatus.FAILED:
            state.overall_status = ProcessStatus.FAILED
            state.add_error(ProcessStage.SPLITTER, result.error_message or "Unknown error")
        
        self.save_document_state(state)
        logger.info(f"Updated splitter result for document: {doc_id}, status: {result.status}")
    
    def update_update_result(
        self,
        doc_id: str,
        result: UpdateResult
    ) -> None:
        """更新入库阶段结果
        
        Args:
            doc_id: 文档ID
            result: 更新结果
        """
        state = self.load_document_state(doc_id)
        if state is None:
            raise ValueError(f"Document state not found: {doc_id}")
        
        state.update_result = result
        
        if result.status == ProcessStatus.SUCCESS:
            state.current_stage = ProcessStage.COMPLETED
            state.overall_status = ProcessStatus.SUCCESS
            state.completed_at = datetime.now()
        else:
            state.overall_status = ProcessStatus.FAILED
            state.add_error(ProcessStage.UPDATE, result.error_message or "Unknown error")
        
        self.save_document_state(state)
        logger.info(f"Updated update result for document: {doc_id}, status: {result.status}")
    
    def mark_stage_failed(
        self,
        doc_id: str,
        stage: ProcessStage,
        error_message: str
    ) -> None:
        """标记某个阶段失败
        
        Args:
            doc_id: 文档ID
            stage: 失败的阶段
            error_message: 错误信息
        """
        state = self.load_document_state(doc_id)
        if state is None:
            raise ValueError(f"Document state not found: {doc_id}")
        
        state.overall_status = ProcessStatus.FAILED
        state.add_error(stage, error_message)
        state.retry_count += 1
        
        self.save_document_state(state)
        logger.error(f"Marked stage {stage.value} as failed for document: {doc_id}")
    
    # ============ 批量处理状态管理 ============
    
    def create_batch_state(
        self,
        batch_name: Optional[str] = None,
        batch_id: Optional[str] = None
    ) -> BatchProcessState:
        """创建批量处理状态
        
        Args:
            batch_name: 批次名称
            batch_id: 批次ID（可选，自动生成）
        
        Returns:
            BatchProcessState: 批量处理状态
        """
        if batch_id is None:
            batch_id = self._generate_batch_id()
        
        batch_state = BatchProcessState(
            batch_id=batch_id,
            batch_name=batch_name or f"Batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        self.save_batch_state(batch_state)
        logger.info(f"Created batch state: {batch_id}")
        return batch_state
    
    def save_batch_state(self, batch_state: BatchProcessState) -> None:
        """保存批量处理状态
        
        Args:
            batch_state: 批量处理状态对象
        """
        batch_state.update_counts()
        file_path = self.batch_states_dir / f"{batch_state.batch_id}.json"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(
                    batch_state.model_dump(mode='json'),
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=str
                )
            logger.debug(f"Saved batch state: {batch_state.batch_id}")
        except Exception as e:
            logger.error(f"Failed to save batch state {batch_state.batch_id}: {e}")
            raise
    
    def load_batch_state(self, batch_id: str) -> Optional[BatchProcessState]:
        """加载批量处理状态
        
        Args:
            batch_id: 批次ID
        
        Returns:
            Optional[BatchProcessState]: 批量处理状态，如果不存在则返回 None
        """
        file_path = self.batch_states_dir / f"{batch_id}.json"
        
        if not file_path.exists():
            logger.warning(f"Batch state not found: {batch_id}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 将 datetime 字符串转换回 datetime 对象
            for field in ['created_at', 'updated_at']:
                if data.get(field):
                    data[field] = datetime.fromisoformat(data[field])
            
            # 转换 doc_states 中的 datetime
            for doc_data in data.get('doc_states', []):
                for field in ['created_at', 'updated_at', 'started_at', 'completed_at']:
                    if doc_data.get(field):
                        doc_data[field] = datetime.fromisoformat(doc_data[field])
            
            batch_state = BatchProcessState(**data)
            logger.debug(f"Loaded batch state: {batch_id}")
            return batch_state
        except Exception as e:
            logger.error(f"Failed to load batch state {batch_id}: {e}")
            raise
    
    # ============ 工具方法 ============
    
    def _generate_doc_id(self) -> str:
        """生成文档ID"""
        return f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    def _generate_batch_id(self) -> str:
        """生成批次ID"""
        return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取状态管理统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        all_states = self.list_document_states()
        
        stats = {
            "total_documents": len(all_states),
            "by_status": {},
            "by_stage": {},
            "storage_size_mb": self._get_storage_size(),
        }
        
        # 按状态统计
        for status in ProcessStatus:
            count = sum(1 for s in all_states if s.overall_status == status)
            stats["by_status"][status.value] = count
        
        # 按阶段统计
        for stage in ProcessStage:
            count = sum(1 for s in all_states if s.current_stage == stage)
            stats["by_stage"][stage.value] = count
        
        return stats
    
    def _get_storage_size(self) -> float:
        """获取存储大小（MB）"""
        total_size = 0
        for file_path in self.storage_dir.rglob("*.json"):
            total_size += file_path.stat().st_size
        return total_size / (1024 * 1024)
    
    def cleanup_completed(self, keep_days: int = 7) -> int:
        """清理已完成的旧状态文件
        
        Args:
            keep_days: 保留最近几天的文件
        
        Returns:
            int: 清理的文件数量
        """
        from datetime import timedelta
        
        cutoff_time = datetime.now() - timedelta(days=keep_days)
        cleaned_count = 0
        
        for state in self.list_document_states():
            if (state.is_completed() and 
                state.completed_at and 
                state.completed_at < cutoff_time):
                if self.delete_document_state(state.doc_id):
                    cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} completed states older than {keep_days} days")
        return cleaned_count