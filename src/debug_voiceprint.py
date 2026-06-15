"""声纹调试脚本 — 检查同一个人说话之间的向量距离"""
import os
import sys
import glob
import numpy as np
from config import VOICEPRINT_MODEL, VOICEPRINT_THRESHOLD, VOICEPRINT_DB
import db
import voiceprint

# 修复 Windows 终端编码
if sys.platform == "win32":
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")

print("=" * 60)
print("声纹向量差异诊断")
print("=" * 60)

# 1. 确保模型加载
voiceprint.load()
pipeline = voiceprint._pipeline
print(f"\n模型: {VOICEPRINT_MODEL}")
print(f"阈值: {VOICEPRINT_THRESHOLD}")

# 2. 找出所有录音文件
recordings = sorted(glob.glob("recording_20260614_223*.wav"))
print(f"\n找到 {len(recordings)} 个录音文件:")
for r in recordings:
    size_kb = os.path.getsize(r) / 1024
    print(f"  {r} ({size_kb:.0f} KB)")

if len(recordings) < 2:
    print("\nWARN:  至少需要 2 个录音文件才能做对比，请先运行 main.py 并多唤醒几次")
    exit()

# 3. 提取每个录音的声纹向量
print("\n--- 提取声纹向量 ---")
embs = {}
for r in recordings:
    emb = voiceprint.extract(r)
    embs[r] = emb
    print(f"  {r}: shape={emb.shape}, norm={np.linalg.norm(emb):.4f}")

# 4. 两两对比（同一人 vs 不同录音）
print("\n--- 两两余弦相似度矩阵 ---")
n = len(recordings)
print(f"{'':>25}", end="")
for i in range(n):
    print(f"  rec{i}", end="")
print()
for i in range(n):
    print(f"  {recordings[i]:>23}", end="")
    for j in range(n):
        sim = float(np.dot(embs[recordings[i]], embs[recordings[j]])
                    / (np.linalg.norm(embs[recordings[i]]) * np.linalg.norm(embs[recordings[j]])))
        marker = ""
        if i == j:
            marker = "   "  # 自己和自己是 1.0
        elif sim < VOICEPRINT_THRESHOLD:
            marker = " !!LOW"  # 低于阈值
        else:
            marker = " OK"
        print(f"  {sim:.3f}{marker}", end="")
    print()

# 5. 检查数据库中的声纹
print(f"\n--- 数据库状态 ---")
db_count = db.count()
print(f"声纹数量: {db_count}")
all_vp = db.list_all()
for vp in all_vp:
    print(f"  id={vp['id']} name='{vp['name']}' created={vp['created_at']}")

# 6. 拿第一个录音模拟 verify 过程
print(f"\n--- 模拟 verify('{recordings[-1]}') ---")
last_emb = embs[recordings[-1]]

# 查库中最佳匹配
best_name, best_sim = db.find_best(last_emb)
print(f"  与库中最匹配: name='{best_name}' sim={best_sim:.4f}")

if best_sim >= VOICEPRINT_THRESHOLD:
    print(f"  OK 会识别为: {best_name}")
else:
    print(f"  !!LOW 低于阈值 {VOICEPRINT_THRESHOLD}，会注册为新人")

# 7. 关键：同一个人不同录音之间的最低/最高/平均相似度
if n >= 2:
    off_diag = []
    for i in range(n):
        for j in range(n):
            if i != j:
                off_diag.append(float(
                    np.dot(embs[recordings[i]], embs[recordings[j]])
                    / (np.linalg.norm(embs[recordings[i]]) * np.linalg.norm(embs[recordings[j]]))
                ))
    print(f"\n--- 同人不同录音相似度统计 ---")
    print(f"  最低: {min(off_diag):.4f}")
    print(f"  最高: {max(off_diag):.4f}")
    print(f"  平均: {sum(off_diag)/len(off_diag):.4f}")
    print(f"  阈值: {VOICEPRINT_THRESHOLD}")
    if max(off_diag) < VOICEPRINT_THRESHOLD:
        print(f"\n  WARN:  即使最像的两个录音相似度 ({max(off_diag):.4f}) 也低于阈值 ({VOICEPRINT_THRESHOLD})")
        print(f"      同一个人永远会被当成陌生人！建议降低阈值或检查模型/VAD参数")
    elif min(off_diag) < VOICEPRINT_THRESHOLD:
        print(f"\n  WARN:  部分录音低于阈值，说明录音之间有较大差异")
        print(f"      可能原因：环境噪声、录音时长不同、VAD切分不稳定")
