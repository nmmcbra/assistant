from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from crawl import crawler
from prettytable import PrettyTable
import time
import os
import logging
from typing import List, Dict

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置常量
CONFIG = {
    "API_BASE_URL": "https://api.moonshot.cn/v1",
    "MODEL_NAME": "moonshot-v1-8k",
    "MAX_HISTORY": 20,
    "API_DELAY": 60,
    "SAFETY_DELAY": 1.0  # 请求间最小间隔
}

class ChatAssistant:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("MOONSHOT_API_KEY", "sk-default-key"),
            base_url=CONFIG["API_BASE_URL"]
        )
        self.last_request_time = 0
        
    def safe_request(self, messages: List[Dict]) -> str:
        """带速率限制的安全请求"""
        elapsed = time.time() - self.last_request_time
        if elapsed < CONFIG["SAFETY_DELAY"]:
            time.sleep(CONFIG["SAFETY_DELAY"] - elapsed)
            
        try:
            response = self.client.chat.completions.create(
                model=CONFIG["MODEL_NAME"],
                messages=messages,
                temperature=0.3
            )
            self.last_request_time = time.time()
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"API请求失败: {str(e)}")
            return "抱歉，当前服务不可用，请稍后再试。"

class ConversationHandler:
    def __init__(self):
        self.assistant = ChatAssistant()
        self.history = []
        
    def add_message(self, role: str, content: str):
        """添加消息到历史记录"""
        self.history.append({"role": role, "content": content})
        # 保持历史记录长度
        if len(self.history) > CONFIG["MAX_HISTORY"] * 2:  # 考虑双方对话
            self.history = self.history[-CONFIG["MAX_HISTORY"]*2:]

    def conduct_intro_phase(self):
        """进行导购阶段对话"""
        print("Kimi: 您好!我是您的购物助手，向我描述您的需求，我将为您推荐商品。"
              "当您决定好要购买的商品时，请说'结束'以开始比价。")
        
        # 初始化系统提示
        system_prompt = (
            "作为商品推荐助手，您需要：\n"
            "1. 通过问诊式对话明确用户需求\n"
            "2. 提供专业购买建议\n"
            "3. 确认用户最终选择\n"
            "对话示例：\n"
            "用户：脚跟被鞋磨\n"
            "助手：建议使用防磨脚贴，需要帮您比较品牌吗？"
        )
        self.add_message("system", system_prompt)

        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                    
                if "结束" in user_input:
                    logger.info("用户结束第一阶段对话")
                    break
                    
                self.add_message("user", user_input)
                response = self.assistant.safe_request(self.history)
                self.add_message("assistant", response)
                print(f"Kimi: {response}")
                
            except KeyboardInterrupt:
                print("\n对话已终止")
                exit()

    def extract_product_keyword(self) -> str:
        """从对话历史提取商品关键词"""
        extraction_prompt = (
            "请从对话历史中提取最终确定的商品名称，格式要求：\n"
            "1. 只输出商品名称\n"
            "2. 用中文双引号包裹\n"
            "3. 必须是单一商品名词\n"
            "示例输出：\"无线蓝牙耳机\""
        )
        messages = self.history[-4:] + [  # 获取最近2轮对话
            {"role": "user", "content": extraction_prompt}
        ]
        result = self.assistant.safe_request(messages)
        
        # 清洗结果
        if "”" in result:
            return result.split("”")[0].replace("“", "")
        return result.strip('"')

    def conduct_comparison_phase(self, products_data: List[Dict]):
        """进行商品比价阶段"""
        print("\n正在分析商品信息...")
        comparison_prompt = (
            "根据以下商品数据进行推荐：\n"
            "1. 排除不符合需求的商品\n"
            "2. 比较价格、评价、服务\n"
            "3. 推荐前三名并说明理由\n"
            "输出格式：\n"
            "- 推荐1：商品名（评分★ 价格链接）\n"
            "- 推荐理由：..."
        )
        
        self.history = [  # 重置对话上下文
            {"role": "system", "content": comparison_prompt},
            {"role": "user", "content": str(products_data)}
        ]
        
        response = self.assistant.safe_request(self.history)
        print(f"\nKimi：根据您的需求，推荐以下商品：\n{response}")

        # 交互式问答
        print("\n您可以继续询问商品细节，或输入'退出'结束会话。")
        while True:
            query = input("\nYou: ").strip()
            if query.lower() in ["退出", "exit"]:
                break
            self.add_message("user", query)
            response = self.assistant.safe_request(self.history)
            self.add_message("assistant", response)
            print(f"Kimi: {response}")

if __name__ == "__main__":
    handler = ConversationHandler()
    
    # 第一阶段：需求确认
    handler.conduct_intro_phase()
    
    # 提取商品关键词
    product_keyword = handler.extract_product_keyword()
    logger.info(f"提取的商品关键词: {product_keyword}")
    
    # 获取商品数据
    logger.info("开始爬取商品信息...")
    try:
        products = crawler(product_keyword)
        logger.info(f"获取到{len(products)}条商品数据")
    except Exception as e:
        logger.error(f"商品获取失败: {str(e)}")
        exit()
    
    # API限速处理
    logger.info(f"等待{CONFIG['API_DELAY']}秒遵守API限制")
    time.sleep(CONFIG["API_DELAY"])
    
    # 第二阶段：商品比价
    handler.conduct_comparison_phase(products)