#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : main.py
@Author  : caixiongjiang
@Date    : 2025/12/29 11:40
@Function: 
    主程序入口
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import logging
from src.utils.log_config import setup_dev_logging, get_logger

# 在程序启动时初始化日志配置
# 这一步会拦截所有标准 logging 到 loguru
setup_dev_logging()

# 获取 logger 实例
logger = get_logger()


def main():
    """主函数"""
    logger.info("程序启动")
    
    # 测试日志功能
    logger.debug("这是 DEBUG 级别的日志")
    logger.info("这是 INFO 级别的日志")
    logger.success("这是 SUCCESS 级别的日志（loguru 特有）")
    logger.warning("这是 WARNING 级别的日志")
    logger.error("这是 ERROR 级别的日志")
    
    # 测试标准 logging（会被拦截到 loguru）
    std_logger = logging.getLogger(__name__)
    std_logger.info("这是标准 logging 的日志，但会被路由到 loguru")
    
    logger.info("程序结束")


if __name__ == "__main__":
    main()
