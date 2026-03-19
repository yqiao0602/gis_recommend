"""
完整流程使用示例

演示如何从自然语言任务描述到QGIS算子链
"""

# TODO: CompletePipeline was moved to legacy/. Update this demo to use InteractiveGISSystem.
# from complete_pipeline import CompletePipeline


def example_1():
    """示例1：空间分析任务"""
    print("\n" + "="*70)
    print("示例1：空间分析任务")
    print("="*70)

    # 初始化流程
    pipeline = CompletePipeline(
        model_checkpoint="outputs/task_conditioned_checkpoints_v3_7_final/best_model.pth",
        llm_api_key="sk-6d6a3478844243979fd29431ce31a841"
    )

    # 处理任务
    result = pipeline.process_task(
        task_desc="在某个点附近100米的范围内选定一个点",
        task_type="Spatial Analysis",
        num_l3_candidates=3,
        num_qgis_candidates=5
    )

    # 保存结果
    if result["success"]:
        pipeline.save_results(result, output_dir="outputs/example1")

    pipeline.close()


def example_2():
    """示例2：水体提取任务"""
    print("\n" + "="*70)
    print("示例2：水体提取任务")
    print("="*70)

    pipeline = CompletePipeline(
        model_checkpoint="outputs/task_conditioned_checkpoints_v3_7_final/best_model.pth",
        llm_api_key="sk-6d6a3478844243979fd29431ce31a841"
    )

    result = pipeline.process_task(
        task_desc="从卫星影像中提取水体并导出为矢量多边形",
        task_type="Waterbody Extraction",
        num_l3_candidates=3,
        num_qgis_candidates=5
    )

    if result["success"]:
        pipeline.save_results(result, output_dir="outputs/example2")

    pipeline.close()


def example_3():
    """示例3：缓冲区分析"""
    print("\n" + "="*70)
    print("示例3：缓冲区分析")
    print("="*70)

    pipeline = CompletePipeline(
        model_checkpoint="outputs/task_conditioned_checkpoints_v3_7_final/best_model.pth",
        llm_api_key="sk-6d6a3478844243979fd29431ce31a841"
    )

    result = pipeline.process_task(
        task_desc="对道路图层创建500米缓冲区，然后与建筑物图层相交",
        task_type="Spatial Analysis",
        num_l3_candidates=3,
        num_qgis_candidates=5
    )

    if result["success"]:
        pipeline.save_results(result, output_dir="outputs/example3")

    pipeline.close()


if __name__ == "__main__":
    # 运行示例
    print("\n" + "="*70)
    print("完整流程示例演示")
    print("="*70)
    print("\n这个脚本演示了如何从自然语言任务描述生成QGIS算子链")
    print("\n包含三个阶段：")
    print("  1. 任务描述 → L3原语序列（使用Transformer模型）")
    print("  2. L3序列 → QGIS算子链（使用Beam Search）")
    print("  3. 生成解释和使用指导（使用LLM）")

    # 选择要运行的示例
    print("\n请选择要运行的示例：")
    print("  1. 空间分析：在某个点附近100米的范围内选定一个点")
    print("  2. 水体提取：从卫星影像中提取水体并导出为矢量多边形")
    print("  3. 缓冲区分析：对道路创建缓冲区并与建筑物相交")
    print("  4. 运行所有示例")

    choice = input("\n请输入选择 (1-4): ").strip()

    if choice == "1":
        example_1()
    elif choice == "2":
        example_2()
    elif choice == "3":
        example_3()
    elif choice == "4":
        example_1()
        example_2()
        example_3()
    else:
        print("无效选择")
