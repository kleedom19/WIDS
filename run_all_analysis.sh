#!/bin/bash
# WiDS Datathon 2025 - Run All Analysis Scripts
# ==============================================

echo "🔥 WiDS Datathon 2025 - Running All Analysis Scripts"
echo "===================================================="
echo ""

echo "Step 1/3: Timeline Analysis..."
python 03_analysis_scripts/eda_1_timeline_analysis.py
echo ""

echo "Step 2/3: Early Signal Validation..."
python 03_analysis_scripts/eda_2_early_signals.py
echo ""

echo "Step 3/3: Geographic Pattern Analysis..."
python 03_analysis_scripts/eda_3_geographic_patterns.py
echo ""

echo "===================================================="
echo "✅ All analyses complete!"
echo ""
echo "Results saved to:"
echo "  📊 04_results/"
echo "  📈 05_visualizations/"
echo ""
echo "Next: Review PROJECT_INDEX.txt for full structure"
echo "===================================================="
