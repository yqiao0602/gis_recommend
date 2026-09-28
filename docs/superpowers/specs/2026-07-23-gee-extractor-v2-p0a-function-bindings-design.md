# GEE Extractor v2 P0-A 函数绑定修复设计

日期：2026-07-23

## 目标

修复 Extractor v2 对源码可静态证明的本地函数绑定召回不足。P0-A 只扩展 helper 注册与展开，不改变调用分类、控制流解释、taxonomy 映射或训练准入。修复后的 evidence 仍是静态源码调用证据，不冒充运行时调用实例或完整 workflow gold。

## 已确认缺口

当前 `_Extractor.functions` 只预注册 `FunctionDeclaration`。因此以下常见 ESTree 形式不会作为 helper 展开：

- `const f = function (...) { ... }`；
- `const f = (...) => ...`；
- `const helpers = { f: function (...) { ... } }`；
- `helpers.f = function (...) { ... }`；
- 上述绑定作为直接调用或 `.map(helper)`、`.iterate(helper)`、`.forEach(helper)` 的命名 callback。

这会稳定遗漏 helper 内的 GEE core、Export 和 presentation 调用。已知受影响样本包括 `script_203101`、`script_210697`、`script_217558`、`script_48309` 和 `script_179599`。

## 方案选择

1. 继续只支持 `FunctionDeclaration`：行为最保守，但已知漏召回无法修复，否决。
2. 建立完整 JavaScript 符号表、作用域和控制流解释器：长期更完整，但超出 P0-A，风险和验证成本过高，否决。
3. 扩展现有静态 helper 表，只登记字面可证明的函数绑定：复用当前内联和递归保护，改动小、可测试，采用。

## 静态绑定规则

- `FunctionDeclaration` 保持当前块级预注册行为。
- 执行到 `VariableDeclaration` 时，如果 declarator 的 `id` 是普通 Identifier 且 `init` 是 `FunctionExpression` 或 `ArrowFunctionExpression`，以变量名登记。
- 如果变量初始化为 `ObjectExpression`，只登记非计算、静态命名且函数值明确的属性，键为 `变量名.属性名`。
- 执行到 `AssignmentExpression` 时，如果左值可由 `_flatten_callee()` 还原为静态 dotted name，右值是函数表达式，则登记该 dotted name。
- 动态计算属性、解构、别名传播、闭包捕获、重新赋值的数据流证明和跨文件绑定均不推断。
- 重复静态名称沿用现有 fail-visible 行为：保留首次绑定并添加 `duplicate_helper_definition`，不静默覆盖。

变量与赋值绑定按源码执行位置登记，不在 Program 开头整体提升。这样不会把 `const`/`let`/赋值函数错误当成 JavaScript 函数声明式提升。

## 调用与 callback 展开

- 直接调用的 callee 经 `_flatten_callee()` 得到静态名称后，若命中 helper 表，则在调用点展开函数体，不把 helper 名记为 GEE 算子。
- 控制容器的命名 callback 参数既可为 Identifier，也可为静态 MemberExpression；名称命中 helper 表时，以 `context=callback` 展开。
- `FunctionExpression` 的 block body 继续走 statement visitor；ArrowFunctionExpression 的 expression body 走 expression visitor。
- `active_helpers` 继续作为递归保护。变量函数或对象属性函数直接或间接递归时，生成 `unresolved/recursive_helper` evidence，禁止无限展开。

## 明确不做

- 不修改 `_classify()`，不处理 `receiver_untyped` 导致的 UI/native JavaScript 假阳性；
- 不根据变量名猜测 `ee.Image`、`ui.Map` 等类型；
- 不计算循环 cardinality，不声称恢复运行时全序；
- 不解析动态属性、动态 import、跨文件 helper 或通用 alias；
- 不修改 legacy extractor、Step2-8、`outputs/` 或 `outputs_v2/`；
- 不调用 LLM、不训练模型、不生成正式训练数据。

## 测试与验收

单元测试必须先证明旧实现对以下行为失败：变量 FunctionExpression 直接调用、变量 ArrowFunctionExpression 直接调用、变量函数作为 `.map` callback、对象属性函数调用、注册 helper 间嵌套调用，以及递归变量 helper 的 unresolved 保护。对象属性覆盖对象字面量；另用赋值形式锁定 `obj.method = function`。

本地验收包括 extractor 专项测试、全部 Extractor v2 相关测试、replay 测试、P0/legacy/provenance 回归、`compileall` 和 `git diff --check`。服务器仅在 `/home/qy` 隔离诊断目录定点重建五个已知失败样本，并复核 `script_4142` 不回退。结果写入独立 P0-A before/after 报告，不写原 `review.csv` 的人工字段，不改变 `training_admission=not_granted`。
