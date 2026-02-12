import json
import logging
import os
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class faceMapping():
    def __init__(self, map_file_path: str):
        self.map_file_path = map_file_path
        self.id_to_name: Dict[str, str] = {}  # 现在是 short_id -> name
        self._load_data()

    def _load_data(self):
        """
        加载 JSON 并构建 {short_id: name} 映射
        假设 JSON 格式为 {"张三": "1478361", ...}
        """
        if not os.path.exists(self.map_file_path):
            logger.error(f"文件未找到: {self.map_file_path}")
            return

        try:
            with open(self.map_file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)  # {"张三": "1478361", ...}

            # 反转为 {"1478361": "张三", ...}
            self.id_to_name = {short_id: name for name, short_id in raw_data.items()}
                
            logger.info(f"已加载 {len(self.id_to_name)} 个用户映射")

        except Exception as e:
            logger.error(f"解析数据失败: {e}")

    def get_user_id(self, face_id: str) -> Optional[str]:
        if not face_id or not isinstance(face_id, str):
            return None

        # 尝试从 face_id 末尾提取不同长度的后缀（常见 6~7 位）
        for length in [7]:  # 可根据实际调整顺序和范围
            if len(face_id) >= length:
                suffix = face_id[-length:]
                if suffix in self.id_to_name:
                    name = self.id_to_name[suffix]
                    logger.info(f"匹配成功: face_id='{face_id}' -> 后缀='{suffix}' -> 用户='{name}'")
                    return name

        logger.warning(f"未找到匹配用户: face_id='{face_id}'")
        return None
    


# ================= 使用示例 =================

# if __name__ == "__main__":
#     map_file = "../data/face_id_person.json" 

    
#     mapper = face_to_user(map_file)
#     name = mapper.get_user_id("Adad123f23-1116881")
#     print(name)  # 输出: 张三