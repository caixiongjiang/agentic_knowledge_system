#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
ParseResult 数据模型测试

测试 ParseResult 及其相关模型的创建、序列化和验证。
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.types.models.parse_result import ParseResult, ParseStatus, ElementInfo, ElementType


class TestParseResult:
    """ParseResult 测试类"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def test_parse_result_creation(self):
        """测试 ParseResult 基本创建"""
        print("\n[测试1] ParseResult 基本创建")
        try:
            result = ParseResult(
                user_id="user_001",
                file_id="file_001",
                document_id="document-test-001",
                filename="test.pdf",
                status=ParseStatus.SUCCESS,
                parse_tool="mineru",
                total_pages=10
            )
            
            assert result.user_id == "user_001"
            assert result.file_id == "file_001"
            assert result.status == ParseStatus.SUCCESS
            assert result.is_success() is True
            assert result.has_images() is False
            assert result.has_tables() is False
            assert result.total_elements == 0
            
            print("✅ 测试通过：ParseResult 基本创建成功")
            self.passed += 1
        except Exception as e:
            print(f"❌ 测试失败：{e}")
            self.errors.append(str(e))
            self.failed += 1
    
    def test_unified_elements(self):
        """测试统一的元素模型"""
        print("\n[测试2] 统一的元素模型")
        try:
            # 创建文本元素
            text_elem = ElementInfo(
                element_id="element-001",
                document_id="document-test-001",
                element_index=0,
                element_type=ElementType.TEXT,
                page_index=0,
                text="This is a text element",
                text_level=1
            )
            
            # 创建图片元素
            image_elem = ElementInfo(
                element_id="element-002",
                document_id="document-test-001",
                element_index=1,
                element_type=ElementType.IMAGE,
                page_index=0,
                bucket_name="test-bucket",
                image_file_path="/path/to/image.png",
                image_file_name="image.png",
                image_file_type="png",
                image_caption="This is an image",
                image_footnote="Image source: test"
            )
            
            # 创建表格元素
            table_elem = ElementInfo(
                element_id="element-003",
                document_id="document-test-001",
                element_index=2,
                element_type=ElementType.TABLE,
                page_index=1,
                table_body="Table body content",
                table_caption="Table 1: Sample table",
                table_footnote="Table footnote"
            )
            
            # 创建 ParseResult
            result = ParseResult(
                user_id="user_001",
                file_id="file_001",
                document_id="document-test-001",
                filename="test.pdf",
                status=ParseStatus.SUCCESS,
                elements=[text_elem, image_elem, table_elem]
            )
            
            # 验证元素统计
            assert result.total_elements == 3
            assert len(result.text_elements) == 1
            assert len(result.image_elements) == 1
            assert len(result.table_elements) == 1
            assert result.has_images() is True
            assert result.has_tables() is True
            
            # 验证元素类型判断
            assert text_elem.is_text() is True
            assert image_elem.is_image() is True
            assert table_elem.is_table() is True
            
            print("✅ 测试通过：统一的元素模型")
            self.passed += 1
        except Exception as e:
            print(f"❌ 测试失败：{e}")
            self.errors.append(str(e))
            self.failed += 1
    
    def test_element_data_conversion(self):
        """测试元素数据转换"""
        print("\n[测试3] 元素数据转换")
        try:
            # 创建元素
            text_elem = ElementInfo(
                element_id="element-001",
                document_id="document-test-001",
                element_index=0,
                element_type=ElementType.TEXT,
                page_index=0,
                text="Sample text",
                text_level=1
            )
            
            image_elem = ElementInfo(
                element_id="element-002",
                document_id="document-test-001",
                element_index=1,
                element_type=ElementType.IMAGE,
                page_index=0,
                bucket_name="test-bucket",
                image_file_path="/path/to/image.png",
                image_file_name="image.png",
                image_file_type="png",
                image_caption="Test image",
                image_footnote="Image footnote"
            )
            
            table_elem = ElementInfo(
                element_id="element-003",
                document_id="document-test-001",
                element_index=2,
                element_type=ElementType.TABLE,
                table_body="Table body",
                table_caption="Table caption",
                table_footnote="Table footnote"
            )
            
            # 测试转换为 MySQL 格式
            mysql_data = text_elem.to_mysql_dict()
            assert mysql_data["element_id"] == "element-001"
            assert mysql_data["document_id"] == "document-test-001"
            assert mysql_data["element_type"] == "text"
            assert mysql_data["text_level"] == 1
            
            # 测试转换为 MongoDB 格式（文本）
            mongo_data = text_elem.to_mongodb_dict()
            assert mongo_data["_id"] == "element-001"
            assert mongo_data["type"] == "text"
            assert mongo_data["content"]["text"] == "Sample text"
            
            # 测试转换为 MongoDB 格式（图片）
            mongo_data_image = image_elem.to_mongodb_dict()
            assert mongo_data_image["_id"] == "element-002"
            assert mongo_data_image["type"] == "image"
            assert mongo_data_image["content"]["image_caption"] == "Test image"
            assert mongo_data_image["content"]["image_footnote"] == "Image footnote"
            
            # 测试转换为 MongoDB 格式（表格）
            mongo_data_table = table_elem.to_mongodb_dict()
            assert mongo_data_table["_id"] == "element-003"
            assert mongo_data_table["type"] == "table"
            assert mongo_data_table["content"]["table_body"] == "Table body"
            assert mongo_data_table["content"]["table_caption"] == "Table caption"
            assert mongo_data_table["content"]["table_footnote"] == "Table footnote"
            
            print("✅ 测试通过：元素数据转换")
            self.passed += 1
        except Exception as e:
            print(f"❌ 测试失败：{e}")
            self.errors.append(str(e))
            self.failed += 1
    
    def test_parse_result_serialization(self):
        """测试 ParseResult 序列化"""
        print("\n[测试4] ParseResult 序列化")
        try:
            # 创建带元素的 ParseResult
            elements = [
                ElementInfo(
                    element_id="element-001",
                    document_id="document-test-001",
                    element_index=0,
                    element_type=ElementType.TEXT,
                    text="Sample text"
                )
            ]
            
            result = ParseResult(
                user_id="user_001",
                file_id="file_001",
                document_id="document-test-001",
                filename="test.pdf",
                status=ParseStatus.SUCCESS,
                elements=elements,
                total_pages=10,
                total_chars=1000
            )
            
            # 测试转换为字典
            result_dict = result.model_dump()
            assert isinstance(result_dict, dict)
            assert result_dict["user_id"] == "user_001"
            assert result_dict["status"] == "success"
            
            # 测试转换为JSON
            result_json = result.model_dump_json()
            assert isinstance(result_json, str)
            
            # 测试从JSON反序列化
            result_loaded = ParseResult.model_validate_json(result_json)
            assert result_loaded.user_id == result.user_id
            assert result_loaded.file_id == result.file_id
            assert len(result_loaded.elements) == 1
            
            print("✅ 测试通过：ParseResult 序列化和反序列化")
            self.passed += 1
        except Exception as e:
            print(f"❌ 测试失败：{e}")
            self.errors.append(str(e))
            self.failed += 1
    
    def test_parse_result_batch_methods(self):
        """测试 ParseResult 批量数据获取方法"""
        print("\n[测试5] ParseResult 批量数据获取方法")
        try:
            # 创建多种类型的元素
            elements = [
                ElementInfo(
                    element_id="element-001",
                    document_id="document-test-001",
                    element_index=0,
                    element_type=ElementType.TEXT,
                    text="Text 1"
                ),
                ElementInfo(
                    element_id="element-002",
                    document_id="document-test-001",
                    element_index=1,
                    element_type=ElementType.IMAGE,
                    bucket_name="test-bucket",
                    image_file_path="/path/to/image.png",
                    image_file_name="image.png",
                    image_caption="Image caption",
                    image_footnote="Image footnote"
                ),
                ElementInfo(
                    element_id="element-003",
                    document_id="document-test-001",
                    element_index=2,
                    element_type=ElementType.TABLE,
                    table_body="Table body",
                    table_caption="Table caption"
                )
            ]
            
            result = ParseResult(
                user_id="user_001",
                file_id="file_001",
                document_id="document-test-001",
                filename="test.pdf",
                status=ParseStatus.SUCCESS,
                elements=elements
            )
            
            # 测试 get_mysql_data
            mysql_data = result.get_mysql_data()
            assert len(mysql_data) == 3
            assert all("element_id" in d for d in mysql_data)
            
            # 测试 get_mongodb_data（所有元素都包含）
            mongo_data = result.get_mongodb_data()
            assert len(mongo_data) == 3  # 文本、图片、表格都包含
            assert all("_id" in d for d in mongo_data)
            
            # 测试 get_element_stats
            stats = result.get_element_stats()
            assert stats["text"] == 1
            assert stats["image"] == 1
            assert stats["table"] == 1
            assert stats["total"] == 3
            
            print("✅ 测试通过：ParseResult 批量数据获取方法")
            self.passed += 1
        except Exception as e:
            print(f"❌ 测试失败：{e}")
            self.errors.append(str(e))
            self.failed += 1
    
    def test_parse_result_summary(self):
        """测试 ParseResult 摘要生成"""
        print("\n[测试6] ParseResult 摘要生成")
        try:
            elements = [
                ElementInfo(
                    element_id="element-001",
                    document_id="document-test-001",
                    element_index=0,
                    element_type=ElementType.TEXT,
                    text="Text"
                ),
                ElementInfo(
                    element_id="element-002",
                    document_id="document-test-001",
                    element_index=1,
                    element_type=ElementType.IMAGE,
                    bucket_name="test-bucket"
                ),
                ElementInfo(
                    element_id="element-003",
                    document_id="document-test-001",
                    element_index=2,
                    element_type=ElementType.IMAGE,
                    bucket_name="test-bucket"
                ),
                ElementInfo(
                    element_id="element-004",
                    document_id="document-test-001",
                    element_index=3,
                    element_type=ElementType.TABLE,
                    table_body="Table body"
                )
            ]
            
            result = ParseResult(
                user_id="user_001",
                file_id="file_001",
                document_id="document-test-001",
                filename="test.pdf",
                status=ParseStatus.SUCCESS,
                total_pages=10,
                total_chars=1000,
                parse_tool="mineru",
                parse_quality=0.95,
                elements=elements
            )
            
            summary = result.get_summary()
            assert isinstance(summary, dict)
            assert summary["file_id"] == "file_001"
            assert summary["text_count"] == 1
            assert summary["image_count"] == 2
            assert summary["table_count"] == 1
            assert summary["total_elements"] == 4
            assert summary["total_pages"] == 10
            assert summary["parse_quality"] == 0.95
            
            print("✅ 测试通过：ParseResult 摘要生成")
            self.passed += 1
        except Exception as e:
            print(f"❌ 测试失败：{e}")
            self.errors.append(str(e))
            self.failed += 1
    
    def test_parse_status_enum(self):
        """测试 ParseStatus 枚举"""
        print("\n[测试7] ParseStatus 枚举")
        try:
            # 测试成功状态
            result_success = ParseResult(
                user_id="user_001",
                file_id="file_001",
                document_id="document-test-001",
                filename="test.pdf",
                status=ParseStatus.SUCCESS
            )
            assert result_success.is_success() is True
            
            # 测试部分成功状态
            result_partial = ParseResult(
                user_id="user_001",
                file_id="file_001",
                document_id="document-test-001",
                filename="test.pdf",
                status=ParseStatus.PARTIAL_SUCCESS
            )
            assert result_partial.is_success() is True
            
            # 测试失败状态
            result_failed = ParseResult(
                user_id="user_001",
                file_id="file_001",
                document_id="document-test-001",
                filename="test.pdf",
                status=ParseStatus.FAILED,
                error_message="Parse failed"
            )
            assert result_failed.is_success() is False
            assert result_failed.error_message == "Parse failed"
            
            print("✅ 测试通过：ParseStatus 枚举")
            self.passed += 1
        except Exception as e:
            print(f"❌ 测试失败：{e}")
            self.errors.append(str(e))
            self.failed += 1
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("开始测试 ParseResult 数据模型（统一元素版本）")
        print("=" * 60)
        
        self.test_parse_result_creation()
        self.test_unified_elements()
        self.test_element_data_conversion()
        self.test_parse_result_serialization()
        self.test_parse_result_batch_methods()
        self.test_parse_result_summary()
        self.test_parse_status_enum()
        
        print("\n" + "=" * 60)
        print(f"测试完成！总计: {self.passed + self.failed} 个测试")
        print(f"✅ 通过: {self.passed}")
        print(f"❌ 失败: {self.failed}")
        
        if self.errors:
            print("\n错误详情:")
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error}")
        
        print("=" * 60)
        
        return self.failed == 0


def main():
    """主函数"""
    tester = TestParseResult()
    success = tester.run_all_tests()
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
