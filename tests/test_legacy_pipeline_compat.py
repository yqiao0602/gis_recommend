import unittest

from gis_recommend.data import (
    enhanced_sequence_cleaner_final,
    pipeline_runner,
    step1_extract_workflows,
    step2_clean_workflows,
    step3_deduplicate,
    step4_standardize_chains,
    step5_convert_dag_format,
    step6_label_with_l3,
    step7_prepare_v4_data,
    step8_clean_v4_data,
)


class LegacyGeePipelineCompatibilityTests(unittest.TestCase):
    def test_historical_module_paths_still_export_main(self):
        modules = [
            enhanced_sequence_cleaner_final,
            pipeline_runner,
            step1_extract_workflows,
            step2_clean_workflows,
            step3_deduplicate,
            step4_standardize_chains,
            step5_convert_dag_format,
            step6_label_with_l3,
            step7_prepare_v4_data,
            step8_clean_v4_data,
        ]
        for module in modules:
            with self.subTest(module=module.__name__):
                self.assertTrue(callable(module.main))

    def test_pipeline_runner_keeps_public_runner_class(self):
        self.assertTrue(hasattr(pipeline_runner, "PipelineRunner"))


if __name__ == "__main__":
    unittest.main()
