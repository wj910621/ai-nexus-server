# 开发指南

> 本文档说明开发规范、代码风格、测试策略与协作流程。

---

## 一、开发规范

### 1.1 Git分支策略

```
main          生产分支，保护分支
├── develop   开发主分支
├── feature/* 功能分支
├── bugfix/*  修复分支
└── hotfix/*  紧急修复
```

**分支命名规范：**
- 功能：`feature/character-lora-training`
- 修复：`bugfix/audio-mix-volume`
- 紧急：`hotfix/render-crash`

### 1.2 Commit规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type：**
- `feat`: 新功能
- `fix`: 修复Bug
- `docs`: 文档
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

**示例：**
```
feat(character): 添加角色LoRA训练功能

- 支持上传多张训练图片
- 自动标注与训练配置
- 训练进度WebSocket推送

Closes #123
```

### 1.3 代码风格

#### Python（后端）
```python
# 使用Black格式化
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']

# 使用isort排序导入
[tool.isort]
profile = "black"

# 使用flake8检查
[tool.flake8]
max-line-length = 88
extend-ignore = "E203"
```

```python
# ✅ 正确的Python风格
from typing import Optional, List
from sqlalchemy.orm import Session

class CharacterService:
    """角色服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_character(
        self,
        user_id: str,
        character_data: dict
    ) -> Character:
        """创建角色"""
        # ...
```

#### TypeScript（前端）
```json
// .eslintrc.json
{
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "prettier"
  ],
  "rules": {
    "@typescript-eslint/no-unused-vars": "error",
    "react/react-in-jsx-scope": "off"
  }
}
```

```typescript
// ✅ 正确的TypeScript风格
import { useState, useEffect } from 'react';
import { Character } from '@/types/character';

interface CharacterListProps {
  projectId: string;
  onSelect?: (character: Character) => void;
}

export function CharacterList({ projectId, onSelect }: CharacterListProps) {
  const [characters, setCharacters] = useState<Character[]>([]);
  
  useEffect(() => {
    fetchCharacters(projectId).then(setCharacters);
  }, [projectId]);
  
  return (
    <div className="character-list">
      {characters.map(char => (
        <CharacterCard 
          key={char.id} 
          character={char}
          onClick={onSelect}
        />
      ))}
    </div>
  );
}
```

---

## 二、测试策略

### 2.1 测试金字塔

```
        /\
       /E2E\        5%  端到端测试
      /------\
     /集成测试\     25%  API集成测试
    /----------\
   /  单元测试  \   70%  纯函数测试
  /--------------\
```

### 2.2 后端测试

```python
# backend/tests/test_character_service.py
import pytest
from app.services.character_service import CharacterService
from app.core.exceptions import InsufficientCreditsError

class TestCharacterService:
    """角色服务测试"""
    
    @pytest.fixture
    async def service(self, db_session):
        return CharacterService(db_session)
    
    @pytest.mark.asyncio
    async def test_create_character_success(self, service, mock_user):
        """测试成功创建角色"""
        # Arrange
        character_data = {
            'name': '测试角色',
            'style': 'anime',
            'gender': 'female'
        }
        
        # Act
        character = await service.create_character(
            user_id=mock_user.id,
            character_data=character_data
        )
        
        # Assert
        assert character.id is not None
        assert character.name == '测试角色'
        assert character.feature_vector is not None
    
    @pytest.mark.asyncio
    async def test_create_character_insufficient_credits(
        self, service, mock_user_no_credits
    ):
        """测试积分不足"""
        with pytest.raises(InsufficientCreditsError):
            await service.create_character(
                user_id=mock_user_no_credits.id,
                character_data={'name': '测试'}
            )
```

### 2.3 前端测试

```typescript
// frontend/src/features/character/__tests__/CharacterCard.test.tsx
import { render, screen } from '@testing-library/react';
import { CharacterCard } from '../CharacterCard';

describe('CharacterCard', () => {
  const mockCharacter = {
    id: '1',
    name: '测试角色',
    style: 'anime',
    main_image_url: 'https://example.com/image.png',
    rating: 4.5,
    usage_count: 10,
    tags: ['二次元', '少女']
  };
  
  it('应该显示角色名称', () => {
    render(<CharacterCard character={mockCharacter} />);
    expect(screen.getByText('测试角色')).toBeInTheDocument();
  });
  
  it('点击时应该调用onSelect', () => {
    const onSelect = jest.fn();
    render(<CharacterCard character={mockCharacter} onClick={onSelect} />);
    
    screen.getByText('测试角色').click();
    expect(onSelect).toHaveBeenCalledWith(mockCharacter);
  });
});
```

### 2.4 运行测试

```bash
# 后端测试
cd backend
pytest tests/ -v --cov=app --cov-report=html

# 前端测试
cd frontend
npm test
npm run test:coverage
```

---

## 三、开发流程

### 3.1 功能开发流程

```
1. 创建Issue       → 描述需求/bug
2. 创建分支        → git checkout -b feature/xxx
3. 编写测试        → TDD: 先写测试
4. 实现功能        → 编写代码
5. 运行测试        → 确保测试通过
6. 代码审查        → 提交PR
7. 合并分支        → 审查通过后合并
8. 部署验证        → CI/CD自动部署
```

### 3.2 PR规范

```markdown
## PR标题
feat(character): 添加角色LoRA训练功能

## 变更说明
- 新增LoRA训练接口
- 支持多图上传与自动标注
- 训练进度WebSocket推送

## 测试情况
- [x] 单元测试通过
- [x] 集成测试通过
- [x] 手动测试通过

## 关联Issue
Closes #123

## 检查清单
- [x] 代码符合风格规范
- [x] 添加了必要的注释
- [x] 更新了相关文档
- [x] 无console.log/print调试代码
```

---

## 四、CI/CD配置

### 4.1 GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov
    
    - name: Run tests
      env:
        DATABASE_URL: postgresql://postgres:test@localhost:5432/test
        REDIS_URL: redis://localhost:6379
      run: |
        cd backend
        pytest tests/ --cov=app --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
  
  frontend-test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Node
      uses: actions/setup-node@v4
      with:
        node-version: '18'
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json
    
    - name: Install dependencies
      run: |
        cd frontend
        npm ci
    
    - name: Lint
      run: |
        cd frontend
        npm run lint
    
    - name: Test
      run: |
        cd frontend
        npm test -- --coverage
    
    - name: Build
      run: |
        cd frontend
        npm run build
```

### 4.2 自动部署

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Build and push Docker images
      run: |
        docker build -t comic-studio/api:latest ./backend
        docker build -t comic-studio/frontend:latest ./frontend
        docker push comic-studio/api:latest
        docker push comic-studio/frontend:latest
    
    - name: Deploy to server
      uses: appleboy/ssh-action@v0.1.10
      with:
        host: ${{ secrets.SERVER_HOST }}
        username: ${{ secrets.SERVER_USER }}
        key: ${{ secrets.SSH_KEY }}
        script: |
          cd /opt/comic-studio
          docker-compose -f docker-compose.prod.yml pull
          docker-compose -f docker-compose.prod.yml up -d
```

---

## 五、性能优化清单

### 5.1 后端优化

- [ ] 数据库查询添加索引
- [ ] 使用`selectinload`避免N+1查询
- [ ] Redis缓存热点数据
- [ ] 异步IO（async/await）
- [ ] 批量操作代替循环
- [ ] 图片上传使用分片上传

### 5.2 前端优化

- [ ] 代码分割（React.lazy）
- [ ] 图片懒加载
- [ ] 虚拟列表（大数据量）
- [ ] 防抖节流（频繁操作）
- [ ] Web Worker（耗时计算）
- [ ] Service Worker（离线缓存）

### 5.3 AI推理优化

- [ ] 半精度推理（fp16）
- [ ] xformers注意力优化
- [ ] CPU offload
- [ ] 批量推理
- [ ] 模型缓存
- [ ] TensorRT加速（生产环境）

---

## 六、调试技巧

### 6.1 后端调试

```python
# 使用ipdb调试
import ipdb; ipdb.set_trace()

# 日志调试
from loguru import logger
logger.debug(f"Processing character: {character_id}")
logger.info(f"Generated image: {image_url}")
logger.error(f"Failed: {error}")
```

### 6.2 前端调试

```typescript
// React DevTools
// 安装React Developer Tools浏览器插件

// 状态调试
import { devtools } from 'zustand/middleware';
const useStore = create(devtools((set) => ({
  // ...
})));
```

### 6.3 性能分析

```python
# 后端性能分析
import cProfile
import pstats

with cProfile.Profile() as pr:
    # 执行需要分析的代码
    pass

stats = pstats.Stats(pr)
stats.sort_stats('cumtime').print_stats(20)
```

---

*本文档最后更新：2026-07-18*
