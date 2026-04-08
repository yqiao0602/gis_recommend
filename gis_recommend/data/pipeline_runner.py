# -*- coding: utf-8 -*-
"""
Pipeline Runner — 数据处理流水线编排器

支持:
  python -m gis_recommend.data.pipeline_runner                          # 全部 8 步
  python -m gis_recommend.data.pipeline_runner --step 3                 # 单步
  python -m gis_recommend.data.pipeline_runner --start 4 --end 6       # 范围
  python -m gis_recommend.data.pipeline_runner --source-dir X --facts-dir Y
"""
import sys
import time
import argparse
from types import SimpleNamespace
from pathlib import Path

from gis_recommend.data import get_step_output_dir


STEP_NAMES = {
    1: "提取工作流",
    2: "清洗工作流",
    3: "去重",
    4: "链式调用标准化",
    5: "转 DAG 格式",
    6: "L3 标注",
    7: "合并 task_metadata",
    8: "最终序列清洗",
}


class PipelineRunner:
    """8-step data processing pipeline orchestrator."""

    def __init__(self, source_dir=None, facts_dir=None, gee_ops=None):
        self.source_dir = source_dir or "/home/yll/GEE/工作流抽取结果"
        self.facts_dir = Path(facts_dir or "/home/yll/GEE/描述性知识抽取汇总")
        self.gee_ops = Path(gee_ops) if gee_ops else None

    def _build_args(self, step: int) -> SimpleNamespace:
        """Build a SimpleNamespace that matches each step's expected args."""
        if step == 1:
            return SimpleNamespace(
                source_dir=self.source_dir,
                output_dir=get_step_output_dir(1),
            )
        if step == 2:
            return SimpleNamespace(
                input_file=get_step_output_dir(1) / "raw_workflows.json",
                output_dir=get_step_output_dir(2),
            )
        if step == 3:
            return SimpleNamespace(
                input_file=get_step_output_dir(2) / "cleaned_workflows.json",
                output_dir=get_step_output_dir(3),
            )
        if step == 4:
            return SimpleNamespace(
                input_file=get_step_output_dir(3) / "final_workflows.json",
                output_dir=get_step_output_dir(4),
                gee_ops=self.gee_ops,
            )
        if step == 5:
            return SimpleNamespace(
                input_file=get_step_output_dir(4) / "standardized_workflows.json",
                output_dir=get_step_output_dir(5),
            )
        if step == 6:
            from gis_recommend.data import get_project_root
            project_root = get_project_root()
            return SimpleNamespace(
                workflow_sequences=get_step_output_dir(5) / "workflow_sequences.json",
                id_mappings=project_root / "outputs" / "id_mappings.json",
                gee_mapping_dir=project_root.parent / "L3_classification" / "GEE",
                output_dir=get_step_output_dir(6),
                verbose=True,
                quiet=False,
            )
        if step == 7:
            return SimpleNamespace(
                facts_dir=self.facts_dir,
                input_file=get_step_output_dir(6) / "labeled_workflows_l3.json",
                output_dir=get_step_output_dir(7),
            )
        if step == 8:
            return SimpleNamespace(
                input_file=get_step_output_dir(7) / "labeled_workflows_l3_v4.json",
                output_dir=get_step_output_dir(8),
            )
        raise ValueError(f"Unknown step: {step}")

    @staticmethod
    def _import_step(n):
        """Lazily import the step module."""
        mod = {
            1: "step1_extract_workflows",
            2: "step2_clean_workflows",
            3: "step3_deduplicate",
            4: "step4_standardize_chains",
            5: "step5_convert_dag_format",
            6: "step6_label_with_l3",
            7: "step7_prepare_v4_data",
            8: "step8_clean_v4_data",
        }[n]
        import importlib
        return importlib.import_module(f"gis_recommend.data.{mod}")

    def run_step(self, n: int):
        """Run a single pipeline step."""
        print(f"\n{'#' * 70}")
        print(f"# Step {n}: {STEP_NAMES[n]}")
        print(f"{'#' * 70}")
        t0 = time.time()
        module = self._import_step(n)
        args = self._build_args(n)
        module.main(args)
        elapsed = time.time() - t0
        print(f"\n[Step {n} completed in {elapsed:.1f}s]")

    def run_range(self, start: int, end: int):
        """Run steps from *start* to *end* inclusive."""
        for n in range(start, end + 1):
            self.run_step(n)

    def run_all(self):
        """Run the complete 8-step pipeline."""
        self.run_range(1, 8)


def main():
    parser = argparse.ArgumentParser(
        description="数据处理流水线编排器 (8 步)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python -m gis_recommend.data.pipeline_runner                    # 全部\n"
            "  python -m gis_recommend.data.pipeline_runner --step 3           # 单步\n"
            "  python -m gis_recommend.data.pipeline_runner --start 4 --end 6  # 范围\n"
        ),
    )
    parser.add_argument("--source-dir", default=None,
                        help="源数据根目录 (default: /home/yll/GEE/工作流抽取结果)")
    parser.add_argument("--facts-dir", default=None,
                        help="facts_summary 目录 (default: /home/yll/GEE/描述性知识抽取汇总)")
    parser.add_argument("--gee-ops", default=None,
                        help="GEE 标准算子库 JSON 路径 (default: 自动查找)")
    parser.add_argument("--step", type=int, default=None,
                        help="只运行指定步骤 (1-8)")
    parser.add_argument("--start", type=int, default=None,
                        help="起始步骤 (配合 --end)")
    parser.add_argument("--end", type=int, default=None,
                        help="结束步骤 (配合 --start)")
    args = parser.parse_args()

    runner = PipelineRunner(
        source_dir=args.source_dir,
        facts_dir=args.facts_dir,
        gee_ops=args.gee_ops,
    )

    t0 = time.time()

    if args.step is not None:
        runner.run_step(args.step)
    elif args.start is not None or args.end is not None:
        start = args.start or 1
        end = args.end or 8
        runner.run_range(start, end)
    else:
        runner.run_all()

    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"Pipeline finished in {elapsed:.1f}s")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
