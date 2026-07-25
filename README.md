# Nigeria Inventory Query System

基于巴基斯坦库存查询系统（mwh-001.github.io/pakistan-inventory-query/mwh.html）的逻辑，为尼日利亚大区定制的物料库存查询工具。

## 系统架构

```
nigeria-inventory-query/
├── nigeria.html              # 前端页面（单页应用）
├── inventory_index.json      # 物料库存数据
├── substitute_map.json       # 物料替代关系
├── in_transit_index.json     # 在途库存数据
└── README.md                 # 说明文档
```

## 核心逻辑

### 1. 查询流程
```
用户输入物料编码 → 查询主物料库存 → 查询替代品库存（双向） → 汇总展示
```

### 2. 数据文件说明

#### inventory_index.json（库存数据）
```json
{
  "物料编码": {
    "仓库名": { "Good": 良品数量 },
    "_desc": "物料描述"
  }
}
```

#### substitute_map.json（替代关系）
```json
{
  "主物料编码": [
    { "code": "替代物料编码", "desc": "描述", "scenario": "Real logistics/Plan" }
  ]
}
```
- 支持**双向查找**：正向（查替代品）+ 反向（查哪些物料把当前物料作为替代品）

#### in_transit_index.json（在途数据）
```json
{
  "物料编码": {
    "仓库名": 在途数量
  }
}
```

### 3. 仓库列表

已预置尼日利亚仓库（可在 nigeria.html 中 `fixedWarehouses` 数组修改）：

| 类型 | 仓库 |
|------|------|
| 主仓 | Nigeria-MWH |
| 区域仓 | NG-Lagos-Main, NG-Abuja-MWH, NG-Kano-MWH, NG-PortHarcourt-MWH, NG-Ibadan-MWH |
| Carlcare | Lagos-Ikeja, Lagos-VI, Abuja, Kano, PortHarcourt, Ibadan, Benin, Kaduna, Maiduguri, Jos, Ilorin, Owerri, Enugu, Abeokuta |
| Advance | Lagos-Ikeja, Lagos-VI, Abuja, Kano, PortHarcourt, Ibadan, Benin, Kaduna, Maiduguri, Jos, Ilorin, Owerri, Enugu, Abeokuta |
| 经销商 | MMT, M&P, PCC, DLI（Lagos/Abuja/Kano/PortHarcourt） |

### 4. 展示逻辑

- **主物料库存**（Main）：直接查询物料编码在各仓库的良品数量
- **替代品库存**（Substitute）：
  - 正向：当前物料的替代品在各仓库的库存
  - 反向：把当前物料作为替代品的其他物料在各仓库的库存
- **在途库存**（In Transit）：单独统计，不与良品合并
- **汇总卡片**：主物料库存 + 替代品库存 + 总可用 + 总在途

### 5. 颜色标识

| 状态 | 颜色 | 条件 |
|------|------|------|
| 库存充足 | 绿色 | Good > 10 |
| 库存偏低 | 橙色 | 0 < Good ≤ 10 |
| 无库存 | 红色 | Good = 0 |

## 部署方式

### 方式一：GitHub Pages（推荐，与巴基斯坦版一致）
1. 创建 GitHub 仓库，如 `yourname/nigeria-inventory-query`
2. 将 4 个文件（nigeria.html + 3 个 json）推送到仓库
3. 在仓库 Settings → Pages 中启用 GitHub Pages
4. 访问 `https://yourname.github.io/nigeria-inventory-query/nigeria.html`

### 方式二：本地部署
1. 将文件放到任意 HTTP 服务器目录
2. 用浏览器打开 nigeria.html
3. 注意：JSON 文件需要通过 HTTP 访问（不能直接 file:// 打开）

### 方式三：内网部署
1. 部署到公司内网服务器（Nginx/Apache）
2. 配置静态文件服务
3. 定期更新 JSON 数据文件

## 数据更新

JSON 数据文件需要定期更新以反映最新库存状态。建议：
- 自动化：编写脚本从 ERP/SAP 系统导出 → 转换为 JSON 格式 → 上传
- 手动：直接编辑 JSON 文件后重新部署

## 与巴基斯坦版的差异

| 项目 | 巴基斯坦版 | 尼日利亚版 |
|------|-----------|-----------|
| 主题色 | 紫色渐变 | 尼日利亚绿白绿 |
| 仓库列表 | 巴基斯坦仓库 | 尼日利亚仓库 |
| 国旗标识 | 无 | 🇳🇬 NIGERIA 徽章 |
| 数据文件 | 巴基斯坦数据 | 需填入尼日利亚数据 |
| 逻辑 | 完全一致 | 完全一致 |

## 注意事项

1. 仓库名称必须与 JSON 数据中的仓库名**完全一致**（大小写敏感）
2. 物料编码为字符串类型（JSON key），不是数字
3. `_desc` 字段是特殊字段，不会被当作仓库处理
4. 替代品查找是双向的，确保 substitute_map.json 中关系正确
5. 在途数据独立于库存数据，两者互不影响
