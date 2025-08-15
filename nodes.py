import sys
import os
import json
#import comfy
import torch
import requests
import hashlib
import random
#import folder_paths

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 配置文件路径
CONFIG_PATH = os.path.join(current_dir, "config.json")
print(f"[TranslateQualityNode] 配置文件路径: {CONFIG_PATH}")


def load_config_from_file():
    """从配置文件加载API密钥"""
    config = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            print(f"[TranslateQualityNode] 从配置文件加载密钥成功")
        except Exception as e:
            print(f"[TranslateQualityNode] 配置文件加载错误: {e}")
    return config


class TranslateAndQualityEnhancer:
    """
    自动翻译（中文->英文）并添加风格化质量增强词
    支持多种风格选择：卡通动漫、赛博朋克、真人写实、风景油画
    """

    # 预定义风格提示词
    STYLE_TAGS = {
        "无": [],
        "卡通动漫": ["anime style", "cartoon", "vibrant colors", "cute", "detailed line art",
                     "smooth shading", "character design", "Japanese animation"],
        "赛博朋克": ["cyberpunk", "neon lights", "futuristic", "sci-fi", "dystopian",
                     "rainy cityscape", "holographic elements", "robotic details"],
        "真人写实": ["photorealistic", "hyperdetailed", "realistic skin texture", "detailed eyes",
                     "cinematic lighting", "DSLR", "shallow depth of field", "portrait photography"],
        "风景油画": ["oil painting", "impressionist style", "landscape", "brush strokes",
                     "textured canvas", "atmospheric perspective", "golden hour lighting"]
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": ""}),
                "enable_translation": ("BOOLEAN", {"default": True}),
                "quality_strength": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "display": "slider"
                }),
                "style": (["无", "卡通动漫", "赛博朋克", "真人写实", "风景油画"], {"default": "真人写实"}),
                "custom_quality": ("STRING", {
                    "multiline": True,
                    "default": "masterpiece, best quality, highres, extremely detailed, 8k"
                }),
            },
            "optional": {
                "api_config": ("CONFIG",),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("enhanced_text",)
    FUNCTION = "process_text"
    CATEGORY = "TranslateQualityNode"

    def process_text(self, text, enable_translation, quality_strength, style, custom_quality, api_config=None):
        # 获取API配置
        config = self.load_config(api_config)

        # 调试输出配置信息
        print("\n===== TranslateQualityNode 配置信息 =====")
        print(f"百度APPID: {config.get('baidu_appid', '未设置')}")
        print(f"百度密钥: {'已设置' if config.get('baidu_key') else '未设置'}")
        print(f"启用翻译: {enable_translation}")
        print(f"质量强度: {quality_strength}")
        print(f"选择风格: {style}")
        print("======================================\n")

        # 翻译处理
        if enable_translation and text.strip():
            if config.get("baidu_appid") and config.get("baidu_key"):
                print(f"[TranslateQualityNode] 使用百度翻译: {text[:30]}...")
                text = self.baidu_translate(text, config["baidu_appid"], config["baidu_key"])
            else:
                print(f"[TranslateQualityNode] 警告: 未配置有效的百度API密钥，跳过翻译")

        # 添加质量词
        enhanced_text = self.add_quality_tags(text, style, custom_quality, quality_strength)

        return (enhanced_text,)

    def load_config(self, api_config=None):
        """加载API配置（优先级：节点输入 > 配置文件 > 环境变量)"""
        config = {}

        # 1. 加载配置文件
        file_config = load_config_from_file()
        config.update(file_config)

        # 2. 环境变量
        env_config = {
            "baidu_appid": os.getenv("BAIDU_TRANSLATE_APPID", ""),
            "baidu_key": os.getenv("BAIDU_TRANSLATE_KEY", "")
        }
        config.update({k: v for k, v in env_config.items() if v})

        # 3. 节点输入配置
        if api_config:
            config.update(api_config)

        return config

    def baidu_translate(self, text, appid, key):
        """使用百度翻译API进行中英翻译"""
        url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
        salt = random.randint(32768, 65536)
        sign_str = appid + text + str(salt) + key
        sign = hashlib.md5(sign_str.encode()).hexdigest()

        params = {
            "q": text,
            "from": "zh",
            "to": "en",
            "appid": appid,
            "salt": salt,
            "sign": sign
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            result = response.json()
            if "trans_result" in result:
                translated = " ".join([res["dst"] for res in result["trans_result"]])
                print(f"[TranslateQualityNode] 翻译结果: {translated[:50]}...")
                return translated
            else:
                error_msg = result.get('error_msg', '未知错误')
                print(f"[TranslateQualityNode] 百度翻译错误: {error_msg}")
        except Exception as e:
            print(f"[TranslateQualityNode] 百度翻译请求错误: {e}")

        return text  # 失败时返回原文

    def add_quality_tags(self, text, style, custom_quality, strength):
        """添加质量增强词，包含风格化标签"""
        # 基础质量词库
        base_quality_tags = [
            "masterpiece", "best quality", "highres", "ultra detailed", "8k resolution",
            "sharp focus", "professional"
        ]

        # 添加风格化标签
        style_tags = self.STYLE_TAGS.get(style, [])

        # 添加自定义词
        custom_tags = [tag.strip() for tag in custom_quality.split(",") if tag.strip()]

        # 合并所有标签并去重
        quality_tags = base_quality_tags + style_tags + custom_tags
        quality_tags = list(dict.fromkeys(quality_tags))

        # 根据强度选择要添加的词数量
        num_tags = max(1, min(len(quality_tags), int(len(quality_tags) * strength)))
        selected_tags = quality_tags[:num_tags]

        # 如果原文为空，只返回质量词
        if not text.strip():
            return ", ".join(selected_tags)

        # 添加到提示词开头
        enhanced = text + ", " + ", ".join(selected_tags)
        print(f"[TranslateQualityNode] 增强后文本: {enhanced[:100]}...")
        return enhanced


# 用于存储API配置的节点
class TranslationConfig:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "baidu_appid": ("STRING", {"default": ""}),
                "baidu_key": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("CONFIG",)
    RETURN_NAMES = ("api_config",)
    FUNCTION = "get_config"
    CATEGORY = "TranslateQualityNode"

    def get_config(self, baidu_appid, baidu_key):
        config = {}
        if baidu_appid: config["baidu_appid"] = baidu_appid
        if baidu_key: config["baidu_key"] = baidu_key
        return (config,)


# 节点注册
NODE_CLASS_MAPPINGS = {
    "TranslateAndQualityEnhancer": TranslateAndQualityEnhancer,
    "TranslationConfig": TranslationConfig
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TranslateAndQualityEnhancer": "翻译+风格化质量增强",
    "TranslationConfig": "百度翻译API配置"
}

print(f"\n### TranslateQualityNode 加载成功 ###")
print(f"节点数量: {len(NODE_CLASS_MAPPINGS)}")
print(f"配置文件路径: {CONFIG_PATH}\n")