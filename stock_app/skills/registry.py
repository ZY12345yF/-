"""
技能注册表 — 动态注册、发现、热插拔

支持:
  • 按名称注册/查找
  • 按类别分组
  • 依赖检查
  • 热插拔 (运行时注册/卸载)
"""
import threading
from typing import Optional

from .base import BaseSkill


class SkillRegistry:
    """技能注册表 — 全局单例"""

    def __init__(self):
        self._lock = threading.RLock()
        self._skills: dict[str, BaseSkill] = {}
        self._by_category: dict[str, list[str]] = {}

    def register(self, skill: BaseSkill) -> BaseSkill:
        """注册技能。返回 skill 本身,方便装饰器用法。"""
        with self._lock:
            if not skill.name:
                raise ValueError(f"技能 {skill} 缺少 name")
            self._skills[skill.name] = skill
            cat = skill.category or "uncategorized"
            if cat not in self._by_category:
                self._by_category[cat] = []
            if skill.name not in self._by_category[cat]:
                self._by_category[cat].append(skill.name)
        return skill

    def unregister(self, name: str) -> bool:
        """卸载技能"""
        with self._lock:
            skill = self._skills.pop(name, None)
            if not skill:
                return False
            cat = skill.category or "uncategorized"
            if cat in self._by_category:
                try:
                    self._by_category[cat].remove(name)
                except ValueError:
                    pass
            return True

    def get(self, name: str) -> Optional[BaseSkill]:
        """获取技能实例"""
        return self._skills.get(name)

    def list_all(self) -> list[str]:
        """列出所有已注册技能名"""
        with self._lock:
            return list(self._skills.keys())

    def list_by_category(self, category: str) -> list[str]:
        """按类别列出技能"""
        with self._lock:
            return list(self._by_category.get(category, []))

    def list_categories(self) -> list[str]:
        """列出所有类别"""
        with self._lock:
            return list(self._by_category.keys())

    def check_dependencies(self, name: str) -> list[str]:
        """检查技能的依赖是否满足。返回缺失的依赖名列表。"""
        skill = self.get(name)
        if not skill:
            return [name]
        missing = []
        for dep in skill.depends_on:
            if dep not in self._skills:
                missing.append(dep)
        return missing

    def get_skill_chain(self, name: str) -> list[str]:
        """获取技能的完整依赖链 (拓扑排序)"""
        visited = set()
        chain = []

        def visit(n):
            if n in visited:
                return
            visited.add(n)
            skill = self.get(n)
            if skill:
                for dep in skill.depends_on:
                    visit(dep)
            chain.append(n)

        visit(name)
        return chain

    def clear(self):
        """清空所有注册 (测试用)"""
        with self._lock:
            self._skills.clear()
            self._by_category.clear()

    def __len__(self):
        return len(self._skills)

    def __contains__(self, name: str):
        return name in self._skills

    def __repr__(self):
        return f"<SkillRegistry: {len(self._skills)} skills, {len(self._by_category)} categories>"
