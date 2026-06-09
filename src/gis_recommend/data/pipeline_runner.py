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

from gis_recommend.data import (
    get_default_gee_skip_list_path,
    get_default_id_mappings_path,
    get_outputs_dir,
    get_step_output_dir,
)


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

    def __init__(self, source_dir=None, facts_dir=None, gee_ops=None,
                 outputs_dir=None, id_mappings=None, skip_list=None,
                 metadata_source_file=None):
        self.source_dir = source_dir or "/home/yll/GEE/工作流抽取结果"
        self.facts_dir = Path(facts_dir or "/home/yll/GEE/描述性知识抽取汇总")
        self.gee_ops = Path(gee_ops) if gee_ops else None
        self.outputs_dir = get_outputs_dir(outputs_dir)
        self.id_mappings = Path(id_mappings) if id_mappings else get_default_id_mappings_path(self.outputs_dir)
        default_skip = get_default_gee_skip_list_path(self.outputs_dir)
        self.skip_list = Path(skip_list) if skip_list else default_skip
        self.metadata_source_file = Path(metadata_source_file) if metadata_source_file else None

    def _step_dir(self, step: int) -> Path:
        return get_step_output_dir(step, self.outputs_dir)

    def _build_args(self, step: int) -> SimpleNamespace:
        """Build a SimpleNamespace that matches each step's expected args."""
        if step == 1:
            return SimpleNamespace(
                source_dir=self.source_dir,
                output_dir=self._step_dir(1),
            )
        if step == 2:
            return SimpleNamespace(
                input_file=self._step_dir(1) / "raw_workflows.json",
                output_dir=self._step_dir(2),
            )
        if step == 3:
            return SimpleNamespace(
                input_file=self._step_dir(2) / "cleaned_workflows.json",
                output_dir=self._step_dir(3),
            )
        if step == 4:
            return SimpleNamespace(
                input_file=self._step_dir(3) / "final_workflows.json",
                output_dir=self._step_dir(4),
                gee_ops=self.gee_ops,
            )
        if step == 5:
            return SimpleNamespace(
                input_file=self._step_dir(4) / "standardized_workflows.json",
                output_dir=self._step_dir(5),
            )
        if step == 6:
            from gis_recommend.data import get_project_root
            project_root = get_project_root()
            return SimpleNamespace(
                workflow_sequences=self._step_dir(5) / "workflow_sequences.json",
                id_mappings=self.id_mappings,
                gee_mapping_dir=project_root.parent / "L3_classification" / "GEE",
                output_dir=self._step_dir(6),
                skip_list=self.skip_list,
                verbose=True,
                quiet=False,
            )
        if step == 7:
            return SimpleNamespace(
                facts_dir=self.facts_dir,
                input_file=self._step_dir(6) / "labeled_workflows_l3.json",
                output_dir=self._step_dir(7),
                metadata_source_file=self.metadata_source_file,
            )
        if step == 8:
            return SimpleNamespace(
                input_file=self._step_dir(7) / "labeled_workflows_l3_v4.json",
                output_dir=self._step_dir(8),
                id_mappings=self.id_mappings,
                skip_list=self.skip_list,
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
        print(f"Outputs dir: {self.outputs_dir}")
        if n == 6:
            print(f"ID mappings: {self.id_mappings}")
            print(f"Skip list  : {self.skip_list or '(none)'}")
        if n == 7 and self.metadata_source_file:
            print(f"Metadata source: {self.metadata_source_file}")
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
    parser.add_argument("--outputs-dir", default=None,
                        help="输出根目录 (default: outputs 或 GIS_OUTPUTS_DIR；v2 用 outputs_v2)")
    parser.add_argument("--id-mappings", default=None,
                        help="Step6 使用的 id_mappings 文件 (default: outputs-dir 下优先 id_mappings_v2.json)")
    parser.add_argument("--skip-list", default=None,
                        help="Step6 使用的 GEE skip list (default: outputs-dir 下 gee_skip_list_v2.json)")
    parser.add_argument("--metadata-source-file", default=None,
                        help="Step7 从已有 V4 文件 graft task_metadata，适合 v2 重建")
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
        outputs_dir=args.outputs_dir,
        id_mappings=args.id_mappings,
        skip_list=args.skip_list,
        metadata_source_file=args.metadata_source_file,
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
