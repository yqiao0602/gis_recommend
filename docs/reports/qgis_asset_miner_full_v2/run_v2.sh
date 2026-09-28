#!/bin/bash
set -u
cd /home/qy/qgis_asset_v2
python3 -W ignore run_qgis_asset_miner_sharded.py run \
  --processing-manifest inputs/processing_manifest_v2.jsonl \
  --api-manifest inputs/api_manifest_v2.jsonl \
  --empty-manifest inputs/empty_manifest.jsonl \
  --output-dir qgis_asset_miner_full_sharded_v2 \
  --miner mine_qgis_assets.py \
  --shard-size 100 \
  --source-root "core_processing=/home/yll/GEE/爬取多源数据源/QGIS_Core_Processing/workflow_scripts" \
  --source-root "github_merge=/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts" \
  --source-root "gitlab_supplement=/home/yll/GEE/爬取多源数据源/QGIS_Plugins_GitLab_Supplement" \
  --source-root "model_tutorial=/home/yll/GEE/爬取多源数据源/QGIS_Model_Tutorial_Workflows/downloaded_scripts(QGIS_Model_Tutorial_Workflows)" \
  --source-root "official_plugins=/home/yll/GEE/爬取多源数据源/QGIS_Official_Plugins/plugin_unpacked" \
  --source-root "pwc_qgis=/home/yll/GEE/爬取gee脚本/爬取PWCQGIS/downloaded_scripts-PWC" \
  --source-root "route_b=/home/yll/GEE/QGIS_ArcGIS_RouteB_Gitee_GitLab/downloaded_scripts" \
  --source-root "textbook_strict=/home/yll/GEE/爬取GIS代码/QGIS_ArcGIS_Textbook_Candidates_Broad/downloaded_scripts_strict" \
  --source-root "zenodo_qgis=/home/yll/GEE/爬取Zenodo网站/zenodo_extracted/QGIS"
echo "MINER_EXIT=$?"
