import json
import logging
import os
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class LocationManager:
    def __init__(self, map_file_path: str):
        self.map_file_path = map_file_path
        self.location_map: Dict[str, str] = {}
        self._load_data()

    def _load_data(self):
        """
        加载并解析地图数据
        """
        if not os.path.exists(self.map_file_path):
            logger.error(f"地图文件未找到: {self.map_file_path}")
            return

        try:
            with open(self.map_file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            self.location_map = raw_data
                
            logger.info(f"已加载 {len(self.location_map)} 个位置点")

        except Exception as e:
            logger.error(f"解析地图数据失败: {e}")

    def get_map_id(self, location_name: str) -> Optional[str]:
        """
        根据位置名称获取 Map ID
        
        :param location_name: 用户口语中的地点 (e.g., "1402", "茶水间")
        :return: Map ID 字符串 或 None
        """
        if not location_name:
            return None
            
        target = location_name.strip()
        
        # 1. 精确匹配
        if target in self.location_map:
            logger.info(f"精确匹配位置: {target} -> {self.location_map[target]}")
            return self.location_map[target]
            
        # 2. 模糊匹配
        for db_name, db_id in self.location_map.items():
            if target in db_name or db_name in target:
                logger.info(f"模糊匹配位置: '{target}' 映射到 '{db_name}' -> {db_id}")
                return db_id
                
        return None


# ================= 使用示例 =================

if __name__ == "__main__":
    map_file = "./data/map_info.json" 
    
    # 初始化管理器
    loc_mgr = LocationManager(map_file)
    
    # 测试查找
    test_locations = ["茶水间", "1402", "王威创", "不存在的地方"]
    
    for loc in test_locations:
        mid = loc_mgr.get_map_id(loc)
        print(f"{loc:<10} -> ID: {mid}")