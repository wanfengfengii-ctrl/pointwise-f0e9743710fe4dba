# 样本来源关联去重器：既有接口与事故

这是内存中的关联证据处理组件，不修改原始样本。输入样本已由上游完成解析；
每条关联证据表示两个来源属于同一簇，证据可被历史更正或撤回。
下游按样本查询簇标识、来源记录数和有符号质控信号合计。
当前部署采用 Euler-tour 森林，事故是撤回后仍有其他证据连接的来源被拆开。

## 公开 Python 入口

`from dedup import Deduper`

`d = Deduper(samples)`：samples 是 dict[str, int]，键是固定样本 ID，值是固定信号。
ID 必须为非空字符串；整数不接受 bool，允许零和负数。空字典合法。
样本 ID、证据 ID 均区分大小写，排序使用 Python 字符串字典序。

`d.apply(rows) -> list[str]`：rows 必须为列表。每项恰含以下五个字段：
`{"id":"e2","rev":2,"u":"c","v":"d","deleted":true}`。
id 为非空字符串；rev 为正整数且不接受 bool；u、v 必须是已声明样本；
deleted 必须为 bool。删除记录也必须带合法端点。
u=v 的自环和不同证据 ID 的平行边合法。
端点字段有序参与版本内容比较，但图的连通语义无向。

每个证据 ID 仅保留最高修订，包括墓碑。较低修订忽略；
同修订同内容忽略，同修订不同内容抛出 ValueError("REVISION_CONFLICT")。
更高修订完整替换旧证据，可以换端点、撤销或复活。
批内证据 ID 不得重复；非法输入抛出 ValueError("INPUT")。
包括过期版本在内，每行必须先满足字段规则。
非法输入或版本冲突时整批拒绝，所有版本和所有查询结果不变。
接受新版本后，返回实际接受的证据 ID，按字符串顺序排序；忽略项不返回。
空批次、旧版本和相同版本重放不改变任何可观察结果。

一次成功 apply 后的有效图恰含各 ID 最高修订中 deleted=false 的无向边。
一次批次中移动、撤回和新增共同决定最终图；中间选用的生成树不影响结果。
允许改变 graph.py、forest.py 等内部实现，保留上述 Deduper 调用方式和异常语义。

`d.read(sample) -> dict`：返回且仅返回
`{"representative":"a","samples":6,"signal":22}`。
representative 是该连通分量内字典序最小的样本 ID；
samples 是其样本数，每个样本恰计一次，signal 是这些样本固定信号之和。
平行边、自环、环上的多重路径均不得重复贡献。
没有有效关联的样本仍是单独一簇。
未知样本或非字符串参数抛出 ValueError("UNKNOWN_SAMPLE")。
随机化只能影响运行时间，不得使结果存在错误概率。

`d.snapshot() -> dict[str, dict]`：按样本 ID 排序返回全部 read 结果，
仅供全量展示和小规模验证。

## 既有增量服务约束

设 N 为固定样本数加已成功接纳过的不同证据 ID 数再加 2。
单证据更新期望摊还 O(log³N)，单样本查询期望 O(logN)，空间 O(NlogN)。
一个含 k 行的合法批次，除输入解码外总更新工作期望摊还 O(k log³N)；
无效输入的逐行检查不要求次线性。初始化及 snapshot 全量展示不计入单样本查询界限。
采用通常的字典访问、键比较及整数运算单位成本模型；
当前调用的输入、输出对象不计入长期索引空间。

复杂度核算必须包含替代证据查找、索引维护、森林操作和汇总维护。
这些界限针对任意合法更新序列，不能用某一固定事故或平均随机图替代。
不得以反复全簇或全图重算兜底；把 BFS 移到查询、缓存或后台仍计入工作。
不预知未来批次。可以采用随机化平衡结构，但连通性和汇总必须精确。
交付的复杂度说明须对应实际源码及维护的不变量，不能只声称使用了某算法。

## 最小业务样例与事故

samples.py 提供完整数据及批次，不读取外部服务。
样本信号为 a=11、b=-3、c=7、d=0、e=5、f=2。

NORMAL 是 a-b、b-c、a-c，撤回 a-b 后仍应得到
a、b、c 同簇：representative=a、samples=3、signal=15。
孤立的 d 得到 representative=d、samples=1、signal=0。

INCIDENT 按证据 ID 依次为 e0:a-b、e1:b-c、e2:c-d、
e3:d-e、e4:e-f、e5:a-f，六个样本连成环。
RETRACTION 将 e2 修订为 rev=2、deleted=true。
撤回后每个样本仍应返回 representative=a、samples=6、signal=22。
当前实现错误地返回 a/b/c 为 a、3、15，d/e/f 为 d、3、7。
随后再撤回 e5 才应真实分成上述两簇；复活 e2 又应合并成六节点簇。

## 已有执行入口

- `python3 checks.py normal`：退出 0，输出 NORMAL_REGRESSION_OK。
- `python3 checks.py repair`：当前退出 1，输出 RETRACTION_COMPONENT_MISMATCH；
  修复后须退出 0，输出 CORRECTION_REGRESSION_OK。
- `python3 checks.py verify`：依次执行 normal 与 repair 的原业务断言。
- `python3 checks.py demo`：输出修订前、后两行 JSON，每行包含 stage 和实际 samples 查询结果。

正常回归须通过，公开故障须修复，不得删除或削弱既有断言。
补充分裂、替代及修订组合验证；交付修复代码与复杂度、验证说明。
保留 .pointwise-runtime.json 的 version=1、kind=cli，setup 为 argv 数组列表，
verify、demo 为直接执行真实验证和演示的 argv。
