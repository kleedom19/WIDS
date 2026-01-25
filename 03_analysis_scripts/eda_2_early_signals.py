"""
WiDS Datathon 2025 - EDA Script 2: Early Signal Validation
============================================================

Purpose: Identify fire characteristics and keywords that predict evacuations

Outputs:
- early_signals_report.csv: Predictive indicators
- signal_viz/: Visualizations
- keyword_analysis.csv: Text pattern analysis

Author: WiDS Team
Date: 2025-01-25
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import json
import os
import re

# Create output directories
os.makedirs('signal_viz', exist_ok=True)

print("🔍 Starting Early Signal Validation...")
print("="*80)

# ============================================================================
# STEP 1: Load Data
# ============================================================================

print("\n1️⃣ Loading data files...")

# Main incident records
geo_events = pd.read_csv('geo_events_geoevent.csv')
geo_events['date_created'] = pd.to_datetime(geo_events['date_created'])
print(f"   ✓ Loaded {len(geo_events):,} geo events")

# Changelog for temporal signals
geo_event_changelog = pd.read_csv('geo_events_geoeventchangelog.csv')
geo_event_changelog['date_created'] = pd.to_datetime(geo_event_changelog['date_created'])
print(f"   ✓ Loaded {len(geo_event_changelog):,} event changes")

# Fire perimeters for growth analysis
fire_perimeters = pd.read_csv('fire_perimeters_gis_fireperimeter.csv')
fire_perimeters['date_created'] = pd.to_datetime(fire_perimeters['date_created'])
fire_perimeters['source_date_current'] = pd.to_datetime(fire_perimeters['source_date_current'])
print(f"   ✓ Loaded {len(fire_perimeters):,} fire perimeters")

# ============================================================================
# STEP 2: Parse JSON Fields
# ============================================================================

print("\n2️⃣ Parsing JSON fields for fire characteristics...")

def safe_json_parse(json_str):
    try:
        return json.loads(json_str) if pd.notna(json_str) else {}
    except:
        return {}

# Extract fire data
geo_events['data_dict'] = geo_events['data'].apply(safe_json_parse)

geo_events['evacuation_orders'] = geo_events['data_dict'].apply(lambda x: x.get('evacuation_orders'))
geo_events['evacuation_warnings'] = geo_events['data_dict'].apply(lambda x: x.get('evacuation_warnings'))
geo_events['acreage'] = geo_events['data_dict'].apply(lambda x: x.get('acreage', 0))
geo_events['containment'] = geo_events['data_dict'].apply(lambda x: x.get('containment', 0))
geo_events['is_prescribed'] = geo_events['data_dict'].apply(lambda x: x.get('is_prescribed', False))

# Create target variable: Did this fire result in evacuations?
geo_events['had_evacuation'] = (
    geo_events['evacuation_orders'].notna() | 
    geo_events['evacuation_warnings'].notna()
)

print(f"   ✓ Target variable created:")
print(f"      Fires with evacuations: {geo_events['had_evacuation'].sum():,}")
print(f"      Fires without evacuations: {(~geo_events['had_evacuation']).sum():,}")

# ============================================================================
# STEP 3: Analyze Fire Size as Predictor
# ============================================================================

print("\n3️⃣ Analyzing fire size as evacuation predictor...")

# Filter to fires with valid acreage data
fires_with_size = geo_events[geo_events['acreage'] > 0].copy()

# Calculate statistics by evacuation status
evac_sizes = fires_with_size[fires_with_size['had_evacuation']]['acreage']
no_evac_sizes = fires_with_size[~fires_with_size['had_evacuation']]['acreage']

print(f"\n   🔥 Fire Sizes by Evacuation Status:")
print(f"      WITH Evacuations:")
print(f"         Mean: {evac_sizes.mean():.1f} acres")
print(f"         Median: {evac_sizes.median():.1f} acres")
print(f"         75th percentile: {evac_sizes.quantile(0.75):.1f} acres")
print(f"\n      WITHOUT Evacuations:")
print(f"         Mean: {no_evac_sizes.mean():.1f} acres")
print(f"         Median: {no_evac_sizes.median():.1f} acres")
print(f"         75th percentile: {no_evac_sizes.quantile(0.75):.1f} acres")

# ============================================================================
# STEP 4: Text/Keyword Analysis
# ============================================================================

print("\n4️⃣ Analyzing incident names for predictive keywords...")

# Combine all text fields for keyword analysis
def extract_keywords(row):
    """Extract potential keyword signals from text fields"""
    text_parts = []
    
    if pd.notna(row['name']):
        text_parts.append(str(row['name']).lower())
    if pd.notna(row['address']):
        text_parts.append(str(row['address']).lower())
        
    return ' '.join(text_parts)

geo_events['text_content'] = geo_events.apply(extract_keywords, axis=1)

# Define high-risk keywords to search for
HIGH_RISK_KEYWORDS = [
    'wind', 'winds', 'windy',
    'rapid', 'fast', 'spread', 'spreading',
    'structure', 'structures', 'home', 'homes', 'building', 'buildings',
    'threat', 'threatens', 'threatening', 'threatened',
    'explosive', 'erratic', 'extreme',
    'canyon', 'hill', 'ridge',  # Topography
    'evacuation', 'evacuate', 'evacuated', 'evacuating',
    'warning', 'order',
    'shelter', 'flee'
]

# Count keyword occurrences by evacuation status
keyword_counts = {}

for keyword in HIGH_RISK_KEYWORDS:
    pattern = r'\b' + keyword + r'\b'  # Word boundary for exact matches
    
    evac_matches = geo_events[geo_events['had_evacuation']]['text_content'].str.contains(
        pattern, case=False, regex=True, na=False
    ).sum()
    
    no_evac_matches = geo_events[~geo_events['had_evacuation']]['text_content'].str.contains(
        pattern, case=False, regex=True, na=False
    ).sum()
    
    total_evac = geo_events['had_evacuation'].sum()
    total_no_evac = (~geo_events['had_evacuation']).sum()
    
    evac_rate = (evac_matches / total_evac * 100) if total_evac > 0 else 0
    no_evac_rate = (no_evac_matches / total_no_evac * 100) if total_no_evac > 0 else 0
    
    keyword_counts[keyword] = {
        'evac_matches': evac_matches,
        'evac_rate': evac_rate,
        'no_evac_matches': no_evac_matches,
        'no_evac_rate': no_evac_rate,
        'enrichment': evac_rate / no_evac_rate if no_evac_rate > 0 else np.inf
    }

# Convert to DataFrame and sort by enrichment
keyword_df = pd.DataFrame(keyword_counts).T.reset_index()
keyword_df.columns = ['keyword', 'evac_count', 'evac_rate_%', 'no_evac_count', 'no_evac_rate_%', 'enrichment_ratio']
keyword_df = keyword_df.sort_values('enrichment_ratio', ascending=False)

print(f"\n   📝 Top Predictive Keywords (by enrichment in evacuated fires):")
print(keyword_df.head(10)[['keyword', 'evac_rate_%', 'no_evac_rate_%', 'enrichment_ratio']].to_string(index=False))

# ============================================================================
# STEP 5: Temporal Patterns in Changelog
# ============================================================================

print("\n5️⃣ Analyzing changelog patterns as early signals...")

# Parse changelog JSON
geo_event_changelog['changes_dict'] = geo_event_changelog['changes'].apply(safe_json_parse)

# Count changes per incident
changes_per_incident = geo_event_changelog.groupby('geo_event_id').size().reset_index()
changes_per_incident.columns = ['geo_event_id', 'num_changes']

# Merge with evacuation status
incident_change_stats = geo_events[['id', 'had_evacuation']].merge(
    changes_per_incident,
    left_on='id',
    right_on='geo_event_id',
    how='left'
)
incident_change_stats['num_changes'] = incident_change_stats['num_changes'].fillna(0)

# Compare change frequency
evac_changes = incident_change_stats[incident_change_stats['had_evacuation']]['num_changes']
no_evac_changes = incident_change_stats[~incident_change_stats['had_evacuation']]['num_changes']

print(f"\n   📊 Changelog Activity by Evacuation Status:")
print(f"      Fires WITH evacuations:")
print(f"         Mean updates: {evac_changes.mean():.2f}")
print(f"         Median updates: {evac_changes.median():.0f}")
print(f"\n      Fires WITHOUT evacuations:")
print(f"         Mean updates: {no_evac_changes.mean():.2f}")
print(f"         Median updates: {no_evac_changes.median():.0f}")

# ============================================================================
# STEP 6: Fire Perimeter Growth Rate Analysis
# ============================================================================

print("\n6️⃣ Analyzing fire growth rates...")

# For fires with multiple perimeter records, calculate growth rate
perimeter_growth = fire_perimeters[fire_perimeters['geo_event_id'].notna()].copy()

# Group by fire and calculate growth
growth_stats = []

for fire_id, group in perimeter_growth.groupby('geo_event_id'):
    if len(group) < 2:
        continue
    
    # Sort by date
    group = group.sort_values('source_date_current')
    
    # Get valid acreage entries
    valid_acres = group[group['source_acres'].notna()]['source_acres']
    valid_dates = group[group['source_acres'].notna()]['source_date_current']
    
    if len(valid_acres) < 2:
        continue
    
    # Calculate growth rate (acres per day)
    first_size = valid_acres.iloc[0]
    last_size = valid_acres.iloc[-1]
    
    time_diff = (valid_dates.iloc[-1] - valid_dates.iloc[0]).total_seconds() / 86400  # days
    
    if time_diff > 0:
        growth_rate = (last_size - first_size) / time_diff
        
        growth_stats.append({
            'geo_event_id': fire_id,
            'initial_acres': first_size,
            'final_acres': last_size,
            'days_tracked': time_diff,
            'acres_per_day': growth_rate
        })

growth_df = pd.DataFrame(growth_stats)

# Merge with evacuation status
growth_with_evac = growth_df.merge(
    geo_events[['id', 'had_evacuation']],
    left_on='geo_event_id',
    right_on='id',
    how='left'
)

if len(growth_with_evac) > 0:
    evac_growth = growth_with_evac[growth_with_evac['had_evacuation']]['acres_per_day']
    no_evac_growth = growth_with_evac[~growth_with_evac['had_evacuation']]['acres_per_day']
    
    print(f"\n   🔥 Fire Growth Rates:")
    print(f"      Fires WITH evacuations:")
    print(f"         Mean: {evac_growth.mean():.1f} acres/day")
    print(f"         Median: {evac_growth.median():.1f} acres/day")
    print(f"\n      Fires WITHOUT evacuations:")
    print(f"         Mean: {no_evac_growth.mean():.1f} acres/day")
    print(f"         Median: {no_evac_growth.median():.1f} acres/day")
else:
    print("   ⚠️ Insufficient perimeter data for growth rate analysis")

# ============================================================================
# STEP 7: Create Visualizations
# ============================================================================

print("\n7️⃣ Creating visualizations...")

sns.set_style("whitegrid")

# VIZ 1: Fire Size Distribution by Evacuation Status
# ----------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 6))

fires_for_plot = fires_with_size[fires_with_size['acreage'] < 10000].copy()  # Remove extreme outliers for viz

sns.boxplot(
    data=fires_for_plot,
    x='had_evacuation',
    y='acreage',
    ax=ax,
    palette=['lightblue', 'coral']
)
ax.set_xlabel('Had Evacuation')
ax.set_ylabel('Fire Size (acres)')
ax.set_title('Fire Size Distribution: Evacuated vs Non-Evacuated Fires')
ax.set_xticklabels(['No', 'Yes'])
plt.tight_layout()
plt.savefig('signal_viz/fire_size_by_evacuation.png', dpi=300)
plt.close()
print("   ✓ Saved fire_size_by_evacuation.png")

# VIZ 2: Top Predictive Keywords
# --------------------------------
fig, ax = plt.subplots(figsize=(10, 6))

top_keywords = keyword_df.head(10).copy()
x_pos = np.arange(len(top_keywords))

ax.barh(x_pos, top_keywords['evac_rate_%'], color='coral', alpha=0.7, label='With Evacuation')
ax.barh(x_pos, top_keywords['no_evac_rate_%'], color='lightblue', alpha=0.7, label='Without Evacuation')

ax.set_yticks(x_pos)
ax.set_yticklabels(top_keywords['keyword'])
ax.set_xlabel('Appearance Rate (%)')
ax.set_title('Top 10 Keywords in Fire Incidents')
ax.legend()
plt.tight_layout()
plt.savefig('signal_viz/keyword_predictors.png', dpi=300)
plt.close()
print("   ✓ Saved keyword_predictors.png")

# VIZ 3: Changelog Activity
# ---------------------------
fig, ax = plt.subplots(figsize=(10, 6))

change_comparison = pd.DataFrame({
    'With Evacuation': [evac_changes.mean()],
    'Without Evacuation': [no_evac_changes.mean()]
})

change_comparison.T.plot(kind='bar', ax=ax, color=['coral', 'lightblue'], legend=False)
ax.set_ylabel('Mean Number of Status Updates')
ax.set_title('Incident Update Frequency by Evacuation Status')
ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
plt.tight_layout()
plt.savefig('signal_viz/changelog_activity.png', dpi=300)
plt.close()
print("   ✓ Saved changelog_activity.png")

# VIZ 4: Fire Growth Rate (if data available)
# ---------------------------------------------
if len(growth_with_evac) > 20:  # Only create if sufficient data
    fig, ax = plt.subplots(figsize=(12, 6))
    
    growth_plot = growth_with_evac[growth_with_evac['acres_per_day'] < 5000].copy()  # Remove outliers
    
    sns.violinplot(
        data=growth_plot,
        x='had_evacuation',
        y='acres_per_day',
        ax=ax,
        palette=['lightblue', 'coral']
    )
    ax.set_xlabel('Had Evacuation')
    ax.set_ylabel('Growth Rate (acres/day)')
    ax.set_title('Fire Growth Rate: Evacuated vs Non-Evacuated Fires')
    ax.set_xticklabels(['No', 'Yes'])
    plt.tight_layout()
    plt.savefig('signal_viz/growth_rate_by_evacuation.png', dpi=300)
    plt.close()
    print("   ✓ Saved growth_rate_by_evacuation.png")

# ============================================================================
# STEP 8: Save Results
# ============================================================================

print("\n8️⃣ Saving analysis results...")

# Save keyword analysis
keyword_df.to_csv('keyword_analysis.csv', index=False)
print("   ✓ Saved keyword_analysis.csv")

# Save early signals summary
signals_summary = pd.DataFrame({
    'signal_type': [
        'fire_size_mean_evac_acres',
        'fire_size_mean_no_evac_acres',
        'changelog_updates_evac_mean',
        'changelog_updates_no_evac_mean',
        'growth_rate_evac_mean_acres_per_day',
        'growth_rate_no_evac_mean_acres_per_day'
    ],
    'value': [
        evac_sizes.mean(),
        no_evac_sizes.mean(),
        evac_changes.mean(),
        no_evac_changes.mean(),
        evac_growth.mean() if len(growth_with_evac) > 0 else np.nan,
        no_evac_growth.mean() if len(growth_with_evac) > 0 else np.nan
    ]
})
signals_summary.to_csv('early_signals_report.csv', index=False)
print("   ✓ Saved early_signals_report.csv")

# ============================================================================
# COMPLETION
# ============================================================================

print("\n" + "="*80)
print("✅ EARLY SIGNAL ANALYSIS COMPLETE!")
print("="*80)
print("\nGenerated Files:")
print("  📊 early_signals_report.csv - Predictive indicator summary")
print("  📋 keyword_analysis.csv - Text pattern analysis")
print("  📁 signal_viz/ - Visualization PNG files")
print("\nKey Insights:")
print(f"  • Fires with evacuations are {evac_sizes.median() / no_evac_sizes.median():.1f}x larger (median)")
print(f"  • Top predictive keyword: '{keyword_df.iloc[0]['keyword']}' (enrichment: {keyword_df.iloc[0]['enrichment_ratio']:.2f}x)")
print(f"  • Evacuated fires have {evac_changes.mean() / no_evac_changes.mean():.1f}x more status updates")
print("\nNext Steps:")
print("  1. Review keyword_analysis.csv for dashboard trigger words")
print("  2. Run eda_3_geographic_patterns.py for regional analysis")
print("="*80)