# T04 训练说明（过程材料，非交付物）

## DoE
- U 空间：50 LHS，E∈[2.5,3.5]e4 MPa，ν∈[0.21,0.39]（论文 Table 1）
- 力学域：每 U 样本 100 LHS，H_ij∈[−0.2,0.2]，F=H+I；det(F)≤1e-3 的丢弃
- 参考应力：T03 `neohooke.pk2_stress`（论文 Eq.(33)，PDF p.11 视觉核验）
- 规模：50×100=5000 点（n_skipped=0），seed=42

## PANN
- 输入 (I1,I2,I3,E,ν) → Ψ；结构 5→175→175→1（论文 Table 2 baseline），softplus
- 输入仿射缩放到 [-1,1]（train min/max）；缩放进 autograd 图，链式法则自动成立
- 应力 S=2∂Ψ/∂C（autograd，create_graph=True 保留到参数的梯度）
- 目标：Voigt S 按 train 集逐分量 std 归一化；loss = MSE（论文 Eq.(12) 加权版）

## 训练
- Adam lr=1e-3, batch=256, epochs=2000, seed=42, torch 2.14.1+cpu, float64
- 90/10 划分（seed 42+1 的 permutation）
- 产物：doe.npz / pann.pt / scaler.npz / loss_history.npz / metrics.json

## 验收
- 测试集应力相对 L2 < 5%（DOD，项目内部阈值）
- stress(C,u) vs 能量中心差分交叉检查（T03 方法），容差 1e-3
- tangent 大/小对称性抽查
