-- ============================================================
-- M3.1.1 种子：星盘深度分析工作流（线性链 tool 排盘 → llm 分维度解读 → llm 汇总报告）
-- 依赖：M2.2 星盘分析师 agent（id=4，star_chart 工具已注册）
-- 执行方式：由 docker/mysql/upgrade/migrate.sh 自动执行，或手动
--       mysql -h 127.0.0.1 -P 3307 -uroot -p < 本文件
-- 说明：幂等（workflow 表无唯一键，用 WHERE NOT EXISTS 防重；
--       workflow_node 有 (workflow_id, node_key) 唯一键，ON DUPLICATE KEY 覆盖）
-- ============================================================

USE `agentforge`;

-- ------------------------------------------------------------
-- 工作流定义（creator=admin，按 username 动态查 id——库内用户 id 不固定；
-- 仅创建者可见，前端用 admin 账号操作）
-- ------------------------------------------------------------
INSERT INTO `workflow` (`name`, `description`, `creator_id`, `status`, `deleted`)
SELECT '星盘深度分析',
       '排盘（star_chart）→ 五维度解读 → 汇总报告。输入出生信息（如 "1994-05-20 14:30 北京"）一键生成完整本命盘分析。',
       (SELECT id FROM `user` WHERE `username` = 'admin' LIMIT 1), 'ACTIVE', 0
WHERE NOT EXISTS (
  SELECT 1 FROM `workflow` WHERE `name` = '星盘深度分析' AND `deleted` = 0
);

-- ------------------------------------------------------------
-- 节点 1：chart（tool star_chart，birthText 模板引用 {message} 运行输入）
-- ------------------------------------------------------------
INSERT INTO `workflow_node` (`workflow_id`, `node_key`, `node_type`, `params`, `next_node`)
SELECT w.id, 'chart', 'tool',
       JSON_OBJECT('tool', 'star_chart', 'payload', JSON_OBJECT('birthText', '{message}')),
       'dimension'
FROM `workflow` w WHERE w.name = '星盘深度分析' AND w.deleted = 0
ON DUPLICATE KEY UPDATE `params` = VALUES(`params`), `next_node` = VALUES(`next_node`);

-- ------------------------------------------------------------
-- 节点 2：dimension（llm 五维度解读，引用 {chart} 前置节点输出）
-- ------------------------------------------------------------
INSERT INTO `workflow_node` (`workflow_id`, `node_key`, `node_type`, `params`, `next_node`)
SELECT w.id, 'dimension', 'llm',
       JSON_OBJECT('prompt',
         '你是「星盘分析师」，资深占星师。以下是排盘工具输出的本命盘结构化数据：\n{chart}\n\n'
         '请按五个维度解读：\n'
         '1) 上升点与四轴：外在形象与人生方向；\n'
         '2) 太阳/月亮/水星/金星/火星：核心性格与自我表达；\n'
         '3) 木星/土星/天王星/海王星/冥王星：成长课题与人生底色；\n'
         '4) 相位：能量互动方式（刑冲表述为成长课题，不恐吓）；\n'
         '5) 宫位分布：人生重心所在。\n'
         '要求：引用具体行星、星座、宫位、相位；理性温和不夸大；每个维度 250-400 字、展开充分；'
         '不涉及健康/寿命类预测；结尾附一句免责声明。'),
       'summary'
FROM `workflow` w WHERE w.name = '星盘深度分析' AND w.deleted = 0
ON DUPLICATE KEY UPDATE `params` = VALUES(`params`), `next_node` = VALUES(`next_node`);

-- ------------------------------------------------------------
-- 节点 3：summary（llm 汇总报告，引用 {dimension} 前置节点输出；终点 next_node=NULL）
-- ------------------------------------------------------------
INSERT INTO `workflow_node` (`workflow_id`, `node_key`, `node_type`, `params`, `next_node`)
SELECT w.id, 'summary', 'llm',
       JSON_OBJECT('prompt',
         '以下是本命盘五个维度的解读：\n{dimension}\n\n'
         '请整合为一份完整的本命盘分析报告。报告必须包含以下六个部分，各部分用 "### 小标题" 分隔：\n'
         '### 一、总览（上升、太阳、月亮各一句话画像）\n'
         '### 二、上升与四轴（外在形象与人生方向）\n'
         '### 三、核心性格（太阳/月亮/水星/金星/火星的落座落宫与相位）\n'
         '### 四、相位与格局（能量互动与整体意义）\n'
         '### 五、宫位分布与人生重心\n'
         '### 六、成长建议（结合盘面给出积极可行的方向）\n'
         '要求：逻辑连贯，与上文不重复原文，篇幅 1800-2800 字（总字数不超过 3000 字），'
         '结尾必须含免责声明（本解读基于占星学理论，仅供自我探索与娱乐参考）。'),
       NULL
FROM `workflow` w WHERE w.name = '星盘深度分析' AND w.deleted = 0
ON DUPLICATE KEY UPDATE `params` = VALUES(`params`), `next_node` = VALUES(`next_node`);
