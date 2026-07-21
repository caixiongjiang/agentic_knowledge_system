#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
KGExtractor Worker

监听: knowledge_base:summary:end
功能: 统一抽取知识三元组 (实体关系、事件实体、事件关系)
输出: knowledge_base:graph:end, db_write:graph:start
"""

from typing import Optional, List, Dict
from loguru import logger

from src.db.kafka.workers.base_worker import BaseWorker
from src.db.kafka.producer import KafkaProducer
from src.db.kafka.topics import KafkaTopics
from src.types.messages.extract import SummaryEndMessage, GraphEndMessage
from src.types.messages.db_write import GraphWriteMessage


class KGExtractorWorker(BaseWorker):
    """
    KGExtractor Worker
    
    职责:
    - 监听 summary:end 事件
    - 加载 Chunk 内容和文件摘要
    - 并发调用 LLM 抽取三元组
    - 统一抽取实体关系、事件实体、事件关系
    - 三元组去重和清洗
    - 发送图谱写入消息
    
    输入消息: SummaryEndMessage
    输出消息: GraphEndMessage, GraphWriteMessage

    下游接通状态：
    - KGExtractor 尚未实现（当前为 mock 数据），暂不发送 GraphWriteMessage 到
      db_write.graph.start（_send_graph_write_message 调用已注释，方法保留），
      避免 neo4j_writer 消费后因 Neo4j 未配置而报错。GraphEndMessage 仍正常
      发送，供 status manager 标记后台阶段完成。待 KGExtractor 落地后取消
      process_message_impl 中 _send_graph_write_message 注释即可接通。
    
    配置要求:
    - 资源: 4 CPU, 8GB RAM
    - 扩容触发: Kafka lag > 50
    """
    
    def __init__(
        self,
        *args,
        kg_extractor_service=None,  # 知识图谱抽取服务
        **kwargs
    ):
        """
        初始化 KGExtractor Worker
        
        Args:
            kg_extractor_service: 知识图谱抽取服务实例（封装所有业务逻辑）
        """
        super().__init__(*args, **kwargs)
        self._kg_service = kg_extractor_service
    
    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.FILE_SUMMARY_END
    
    async def process_message_impl(self, message: SummaryEndMessage) -> bool:
        """
        处理摘要完成消息,抽取知识图谱
        
        Args:
            message: SummaryEndMessage
            
        Returns:
            bool: 是否处理成功
        """
        logger.info(
            f"开始抽取知识图谱: user_id={message.user_id}, file_id={message.file_id}"
        )
        
        try:
            # TODO: 调用 KGExtractorService 处理业务逻辑
            # kg_result = await self._kg_service.extract_knowledge_graph(
            #     file_id=message.file_id,
            #     file_summary=message.file_summary,
            #     user_id=message.user_id
            # )
            
            # 临时模拟数据（等待 Service 实现）
            cleaned_triples = [
                {"head": f"实体{i}", "relation": "关系", "tail": f"实体{i+1}", "type": "entity_relation"}
                for i in range(10)
            ]
            stats = {
                "entity_count": 11,
                "relation_count": 10,
                "unique_relation_types": 1,
                "entity_types": {},
                "relation_types": {}
            }
            
            # 发送 GraphWriteMessage
            # 图谱抽取尚未实现（当前为 mock 数据），暂不发送 GraphWriteMessage，
            # 避免 neo4j_writer 消费后因 Neo4j 未配置而报错。待 KGExtractor 落地后取消注释。
            # await self._send_graph_write_message(message, cleaned_triples)

            # 发送 GraphEndMessage
            await self._send_graph_end_message(message, stats)
            
            logger.info(
                f"知识图谱抽取完成: file_id={message.file_id}, "
                f"entities={stats['entity_count']}, relations={stats['relation_count']}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"知识图谱抽取失败: file_id={message.file_id}, error={e}",
                exc_info=True
            )
            return False
    
    async def _send_graph_write_message(
        self,
        message: SummaryEndMessage,
        triples: List[Dict]
    ) -> None:
        """
        发送图谱写入消息
        
        Args:
            message: 原始消息
            triples: 三元组列表
        """
        if not self._producer:
            logger.warning("Producer 未配置,无法发送消息")
            return
        
        graph_write_msg = GraphWriteMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            entities=[
                {"name": t["head"], "type": "entity"}
                for t in triples
            ],
            relations=triples,
            batch_size=500,
            priority=1
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.DB_WRITE_GRAPH,
            message=graph_write_msg
        )
        
        logger.debug(f"发送 GraphWriteMessage: {len(triples)} triples")
    
    async def _send_graph_end_message(
        self,
        message: SummaryEndMessage,
        stats: Dict
    ) -> None:
        """
        发送图谱抽取完成消息
        
        Args:
            message: 原始消息
            stats: 统计信息
        """
        if not self._producer:
            logger.warning("Producer 未配置,无法发送消息")
            return
        
        graph_end_msg = GraphEndMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            entities=[],  # 已发送到 GraphWrite,这里不重复
            relations=[],
            graph_stats=stats,
            extraction_quality=0.90,
            llm_model="gpt-4",
            tokens_used={"input": 2000, "output": 500},
            entity_types=stats["entity_types"],
            relation_types=stats["relation_types"]
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.GRAPH_END,
            message=graph_end_msg
        )
        
        logger.debug(f"发送 GraphEndMessage: file_id={message.file_id}")
