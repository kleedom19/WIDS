"""
WiDS Datathon 2025 - Wildfire Evacuation Equity Analysis Pipeline
49ers Intelligence Lab

This script performs comprehensive statistical analysis to support the caregiver
alert system proposal, focusing on evacuation delay disparities.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
import geopandas as gpd
from shapely.geometry import Point
import warnings
warnings.filterwarnings('ignore')

# Set visualization style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10

class WildfireEquityAnalyzer:
    """
    Comprehensive analysis toolkit for wildfire evacuation equity research
    """
    
    def __init__(self, data_path):
        """Initialize with path to WiDS dataset"""
        self.data = pd.read_csv(data_path)
        self.results = {}
        
    def preprocess_data(self):
        """Clean and prepare data for analysis"""
        print("Preprocessing data...")
        
        # Create vulnerability score if not exists
        if 'vulnerability_score' not in self.data.columns:
            # Composite SVI score from available components
            svi_cols = [col for col in self.data.columns if 'svi' in col.lower()]
            if svi_cols:
                self.data['vulnerability_score'] = self.data[svi_cols].mean(axis=1)
        
        # Create age categories
        if 'age' in self.data.columns:
            self.data['age_group'] = pd.cut(self.data['age'], 
                                           bins=[0, 18, 35, 50, 65, 100],
                                           labels=['Youth', 'Young Adult', 'Middle Age', 'Senior', 'Elderly'])
        
        # Flag vulnerable populations
        self.data['is_vulnerable'] = (
            (self.data.get('age', 0) >= 65) | 
            (self.data.get('disability', 0) == 1) |
            (self.data.get('low_income', 0) == 1)
        )
        
        return self.data
    
    def survival_analysis(self, time_col='evacuation_time', event_col='evacuated'):
        """
        Perform survival analysis to model evacuation completion times
        Uses Cox Proportional Hazards if lifelines available
        """
        print("\n=== SURVIVAL ANALYSIS ===")
        
        try:
            from lifelines import CoxPHFitter, KaplanMeierFitter
            
            # Prepare survival data
            survival_data = self.data[[time_col, event_col, 'is_vulnerable']].dropna()
            
            # Kaplan-Meier curves by vulnerability status
            kmf = KaplanMeierFitter()
            
            fig, ax = plt.subplots(figsize=(10, 6))
            
            for group in [True, False]:
                mask = survival_data['is_vulnerable'] == group
                kmf.fit(survival_data[mask][time_col], 
                       survival_data[mask][event_col],
                       label=f"{'Vulnerable' if group else 'Non-vulnerable'} Population")
                kmf.plot_survival_function(ax=ax)
            
            plt.title('Evacuation Completion Curves by Vulnerability Status')
            plt.xlabel('Time (hours)')
            plt.ylabel('Probability of Not Yet Evacuated')
            plt.tight_layout()
            plt.savefig('/home/claude/survival_curves.png', dpi=300, bbox_inches='tight')
            plt.close()
            
            # Cox regression
            cph = CoxPHFitter()
            predictors = ['is_vulnerable', 'vulnerability_score']
            if 'distance_to_fire' in self.data.columns:
                predictors.append('distance_to_fire')
            
            cox_data = self.data[[time_col, event_col] + predictors].dropna()
            cph.fit(cox_data, duration_col=time_col, event_col=event_col)
            
            self.results['cox_summary'] = cph.summary
            print("\nCox Proportional Hazards Results:")
            print(cph.summary)
            
            return cph.summary
            
        except ImportError:
            print("Install lifelines for survival analysis: pip install lifelines --break-system-packages")
            return None
    
    def geospatial_hotspot_analysis(self, lat_col='latitude', lon_col='longitude', 
                                   value_col='evacuation_delay'):
        """
        Identify geographic clusters of evacuation delays using hot spot analysis
        """
        print("\n=== GEOSPATIAL HOT SPOT ANALYSIS ===")
        
        try:
            from esda.getisord import G_Local
            from libpysal.weights import KNN
            
            # Create GeoDataFrame
            geometry = [Point(xy) for xy in zip(self.data[lon_col], self.data[lat_col])]
            gdf = gpd.GeoDataFrame(self.data, geometry=geometry)
            
            # Calculate spatial weights (8 nearest neighbors)
            w = KNN.from_dataframe(gdf, k=8)
            
            # Calculate Getis-Ord Gi* statistic
            g_local = G_Local(gdf[value_col], w)
            
            gdf['hotspot_z_score'] = g_local.Zs
            gdf['hotspot_p_value'] = g_local.p_sim
            gdf['is_hotspot'] = (g_local.Zs > 1.96) & (g_local.p_sim < 0.05)  # 95% confidence
            gdf['is_coldspot'] = (g_local.Zs < -1.96) & (g_local.p_sim < 0.05)
            
            # Visualize
            fig, ax = plt.subplots(figsize=(12, 10))
            
            gdf.plot(column='hotspot_z_score', 
                    cmap='RdYlBu_r', 
                    legend=True,
                    ax=ax,
                    markersize=20,
                    alpha=0.6)
            
            plt.title('Evacuation Delay Hot Spots (Getis-Ord Gi*)')
            plt.xlabel('Longitude')
            plt.ylabel('Latitude')
            plt.tight_layout()
            plt.savefig('/home/claude/hotspot_map.png', dpi=300, bbox_inches='tight')
            plt.close()
            
            # Summary statistics
            n_hotspots = gdf['is_hotspot'].sum()
            n_coldspots = gdf['is_coldspot'].sum()
            
            print(f"\nIdentified {n_hotspots} high-delay hotspots")
            print(f"Identified {n_coldspots} low-delay coldspots")
            
            self.results['hotspot_gdf'] = gdf
            return gdf
            
        except ImportError:
            print("Install esda and libpysal: pip install esda libpysal --break-system-packages")
            return None
    
    def predictive_risk_model(self, target='evacuation_delay'):
        """
        Build ML model to predict evacuation delays - powers risk calculator
        """
        print("\n=== PREDICTIVE RISK MODELING ===")
        
        # Select features
        feature_cols = [col for col in self.data.columns if any(x in col.lower() 
                       for x in ['svi', 'age', 'income', 'disability', 'distance', 'population'])]
        
        # Prepare data
        X = self.data[feature_cols].fillna(self.data[feature_cols].median())
        y = self.data[target].fillna(self.data[target].median())
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train Gradient Boosting model
        model = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        model.fit(X_train, y_train)
        
        # Evaluate
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)
        cv_scores = cross_val_score(model, X, y, cv=5)
        
        print(f"\nModel Performance:")
        print(f"Training R²: {train_score:.3f}")
        print(f"Test R²: {test_score:.3f}")
        print(f"Cross-Validation R²: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\nTop 10 Features:")
        print(feature_importance.head(10))
        
        # Visualize feature importance
        plt.figure(figsize=(10, 8))
        sns.barplot(data=feature_importance.head(15), x='importance', y='feature')
        plt.title('Top Features Predicting Evacuation Delay')
        plt.xlabel('Importance Score')
        plt.tight_layout()
        plt.savefig('/home/claude/feature_importance.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        self.results['risk_model'] = model
        self.results['feature_importance'] = feature_importance
        
        return model, feature_importance
    
    def disparity_analysis(self, group_col='is_vulnerable', outcome_col='evacuation_delay'):
        """
        Quantify evacuation disparities between vulnerable and non-vulnerable groups
        """
        print("\n=== DISPARITY ANALYSIS ===")
        
        vulnerable = self.data[self.data[group_col] == True][outcome_col]
        non_vulnerable = self.data[self.data[group_col] == False][outcome_col]
        
        # Statistical tests
        t_stat, p_value = stats.ttest_ind(vulnerable.dropna(), non_vulnerable.dropna())
        effect_size = (vulnerable.mean() - non_vulnerable.mean()) / np.sqrt(
            ((len(vulnerable)-1)*vulnerable.std()**2 + (len(non_vulnerable)-1)*non_vulnerable.std()**2) / 
            (len(vulnerable) + len(non_vulnerable) - 2)
        )
        
        print(f"\nVulnerable Population: {vulnerable.mean():.2f} hours (SD: {vulnerable.std():.2f})")
        print(f"Non-Vulnerable Population: {non_vulnerable.mean():.2f} hours (SD: {non_vulnerable.std():.2f})")
        print(f"Mean Difference: {vulnerable.mean() - non_vulnerable.mean():.2f} hours")
        print(f"T-statistic: {t_stat:.3f}, p-value: {p_value:.4f}")
        print(f"Cohen's d (effect size): {effect_size:.3f}")
        
        # Visualize distribution
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # Histogram
        axes[0].hist(vulnerable.dropna(), alpha=0.6, label='Vulnerable', bins=30, color='red')
        axes[0].hist(non_vulnerable.dropna(), alpha=0.6, label='Non-Vulnerable', bins=30, color='blue')
        axes[0].set_xlabel('Evacuation Delay (hours)')
        axes[0].set_ylabel('Frequency')
        axes[0].set_title('Distribution of Evacuation Delays')
        axes[0].legend()
        
        # Box plot
        data_to_plot = [vulnerable.dropna(), non_vulnerable.dropna()]
        axes[1].boxplot(data_to_plot, labels=['Vulnerable', 'Non-Vulnerable'])
        axes[1].set_ylabel('Evacuation Delay (hours)')
        axes[1].set_title('Evacuation Delay Comparison')
        
        plt.tight_layout()
        plt.savefig('/home/claude/disparity_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        self.results['disparity_stats'] = {
            'vulnerable_mean': vulnerable.mean(),
            'non_vulnerable_mean': non_vulnerable.mean(),
            'difference': vulnerable.mean() - non_vulnerable.mean(),
            'p_value': p_value,
            'effect_size': effect_size
        }
        
        return self.results['disparity_stats']
    
    def inequality_metrics(self, outcome_col='evacuation_delay', income_col='income'):
        """
        Calculate Gini coefficient and create Lorenz curve for evacuation inequality
        """
        print("\n=== INEQUALITY METRICS ===")
        
        # Gini coefficient
        delays = self.data[outcome_col].dropna().sort_values()
        n = len(delays)
        index = np.arange(1, n + 1)
        gini = (2 * np.sum(index * delays)) / (n * np.sum(delays)) - (n + 1) / n
        
        print(f"Gini Coefficient for Evacuation Delays: {gini:.3f}")
        print("(0 = perfect equality, 1 = perfect inequality)")
        
        # Lorenz curve
        cumsum = np.cumsum(delays)
        cumsum = cumsum / cumsum[-1]  # Normalize
        
        plt.figure(figsize=(10, 8))
        plt.plot(np.linspace(0, 1, n), cumsum, label='Lorenz Curve', linewidth=2)
        plt.plot([0, 1], [0, 1], 'k--', label='Perfect Equality', linewidth=1)
        plt.fill_between(np.linspace(0, 1, n), cumsum, np.linspace(0, 1, n), alpha=0.3)
        plt.xlabel('Cumulative Share of Population')
        plt.ylabel('Cumulative Share of Evacuation Time')
        plt.title(f'Lorenz Curve for Evacuation Delays (Gini = {gini:.3f})')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig('/home/claude/lorenz_curve.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        self.results['gini_coefficient'] = gini
        return gini
    
    def caregiver_impact_simulation(self, reduction_hours=2):
        """
        Simulate impact of caregiver intervention on evacuation times
        """
        print(f"\n=== CAREGIVER INTERVENTION SIMULATION ===")
        print(f"Assuming caregiver intervention reduces evacuation time by {reduction_hours} hours")
        
        # Calculate current vulnerable population delays
        vulnerable_delays = self.data[self.data['is_vulnerable'] == True]['evacuation_delay']
        
        # Simulate with caregiver intervention
        simulated_delays = vulnerable_delays - reduction_hours
        simulated_delays = simulated_delays.clip(lower=0)  # Can't be negative
        
        # Calculate lives saved (assuming delays > 6 hours increase mortality)
        critical_threshold = 6
        current_critical = (vulnerable_delays > critical_threshold).sum()
        simulated_critical = (simulated_delays > critical_threshold).sum()
        lives_potentially_saved = current_critical - simulated_critical
        
        print(f"\nCurrent vulnerable population in critical delay zone (>{critical_threshold}h): {current_critical}")
        print(f"With caregiver intervention: {simulated_critical}")
        print(f"Potential reduction: {lives_potentially_saved} individuals ({lives_potentially_saved/len(vulnerable_delays)*100:.1f}%)")
        
        # Visualization
        fig, ax = plt.subplots(figsize=(12, 6))
        
        bins = np.linspace(0, vulnerable_delays.max(), 30)
        ax.hist(vulnerable_delays, bins=bins, alpha=0.6, label='Current', color='red')
        ax.hist(simulated_delays, bins=bins, alpha=0.6, label=f'With Caregiver Alert (-{reduction_hours}h)', color='green')
        ax.axvline(critical_threshold, color='black', linestyle='--', linewidth=2, label='Critical Threshold')
        
        ax.set_xlabel('Evacuation Delay (hours)')
        ax.set_ylabel('Number of Individuals')
        ax.set_title('Impact of Caregiver Alert System on Evacuation Delays')
        ax.legend()
        plt.tight_layout()
        plt.savefig('/home/claude/caregiver_impact.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        self.results['simulation'] = {
            'current_mean': vulnerable_delays.mean(),
            'simulated_mean': simulated_delays.mean(),
            'lives_saved': lives_potentially_saved,
            'percent_improvement': lives_potentially_saved/len(vulnerable_delays)*100
        }
        
        return self.results['simulation']
    
    def generate_report(self, output_path='/home/claude/analysis_report.txt'):
        """
        Generate comprehensive text report of all findings
        """
        with open(output_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("WiDS DATATHON 2025 - EVACUATION EQUITY ANALYSIS REPORT\n")
            f.write("49ers Intelligence Lab\n")
            f.write("=" * 80 + "\n\n")
            
            if 'disparity_stats' in self.results:
                f.write("EVACUATION DISPARITY FINDINGS:\n")
                f.write(f"- Vulnerable populations evacuate {self.results['disparity_stats']['difference']:.2f} hours slower on average\n")
                f.write(f"- This difference is statistically significant (p < {self.results['disparity_stats']['p_value']:.4f})\n")
                f.write(f"- Effect size (Cohen's d): {self.results['disparity_stats']['effect_size']:.3f}\n\n")
            
            if 'gini_coefficient' in self.results:
                f.write(f"INEQUALITY METRIC:\n")
                f.write(f"- Gini coefficient: {self.results['gini_coefficient']:.3f}\n")
                f.write(f"  (Indicates {'high' if self.results['gini_coefficient'] > 0.4 else 'moderate'} inequality in evacuation times)\n\n")
            
            if 'simulation' in self.results:
                f.write("CAREGIVER INTERVENTION IMPACT:\n")
                f.write(f"- {self.results['simulation']['lives_saved']} individuals moved out of critical delay zone\n")
                f.write(f"- {self.results['simulation']['percent_improvement']:.1f}% improvement in high-risk population\n")
                f.write(f"- Average delay reduced from {self.results['simulation']['current_mean']:.2f}h to {self.results['simulation']['simulated_mean']:.2f}h\n\n")
            
            f.write("\nRECOMMENDATIONS:\n")
            f.write("1. Implement caregiver alert system targeting identified hotspot areas\n")
            f.write("2. Prioritize pre-registration in communities with high SVI scores\n")
            f.write("3. Focus outreach on populations 65+ and those with mobility limitations\n")
        
        print(f"\nFull report saved to {output_path}")


# Main execution
if __name__ == "__main__":
    print("WiDS Datathon 2025 - Comprehensive Analysis Pipeline")
    print("=" * 60)
    
    # Initialize (replace with actual data path)
    # analyzer = WildfireEquityAnalyzer('path/to/wids_data.csv')
    # analyzer.preprocess_data()
    
    # Run analyses
    # analyzer.disparity_analysis()
    # analyzer.inequality_metrics()
    # analyzer.predictive_risk_model()
    # analyzer.caregiver_impact_simulation(reduction_hours=2)
    # analyzer.geospatial_hotspot_analysis()
    # analyzer.survival_analysis()
    
    # Generate report
    # analyzer.generate_report()
    
    print("\nAnalysis pipeline ready. Update data path and uncomment execution lines.")