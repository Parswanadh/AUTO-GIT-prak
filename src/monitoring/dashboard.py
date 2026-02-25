"""
Dashboard Generator - Integration #14

Generates HTML dashboards with charts for monitoring:
- Performance metrics (latency, throughput)
- Quality trends
- Error rates
- Cost tracking
- Integration-specific views
"""

import json
from datetime import datetime
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class DashboardGenerator:
    """Generate HTML dashboards with embedded charts."""
    
    def __init__(self):
        """Initialize dashboard generator."""
        pass
    
    def generate_dashboard(self, metrics: Dict[str, Any]) -> str:
        """
        Generate complete HTML dashboard.
        
        Args:
            metrics: Dictionary of metrics from MetricsCollector
            
        Returns:
            HTML string
        """
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Production Monitoring Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        {self._get_styles()}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 Production Monitoring Dashboard</h1>
            <p class="timestamp">Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p class="time-window">Time Window: {metrics.get('time_window', '1h')}</p>
        </header>
        
        {self._generate_overview_section(metrics)}
        {self._generate_performance_section(metrics)}
        {self._generate_quality_section(metrics)}
        {self._generate_reliability_section(metrics)}
        {self._generate_integrations_section(metrics)}
        {self._generate_backends_section(metrics)}
        
        <footer>
            <p>Auto-Git Production Monitoring System - Integration #14</p>
        </footer>
    </div>
    
    <script>
        {self._generate_chart_scripts(metrics)}
    </script>
</body>
</html>
"""
        return html
    
    def _get_styles(self) -> str:
        """Get CSS styles for dashboard."""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            padding: 40px;
        }
        
        header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #667eea;
        }
        
        h1 {
            font-size: 2.5em;
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .timestamp {
            color: #666;
            font-size: 0.9em;
        }
        
        .time-window {
            color: #999;
            font-size: 0.85em;
            margin-top: 5px;
        }
        
        section {
            margin-bottom: 40px;
        }
        
        h2 {
            font-size: 1.8em;
            color: #333;
            margin-bottom: 20px;
            border-left: 5px solid #667eea;
            padding-left: 15px;
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
        }
        
        .metric-label {
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 8px;
        }
        
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
        }
        
        .metric-unit {
            font-size: 0.6em;
            opacity: 0.8;
        }
        
        .chart-container {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
        }
        
        canvas {
            max-width: 100%;
        }
        
        .status-good { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
        .status-warning { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
        .status-error { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }
        
        .error-list {
            background: #fff5f5;
            border-left: 4px solid #e53e3e;
            padding: 15px 20px;
            border-radius: 8px;
        }
        
        .error-item {
            padding: 8px 0;
            border-bottom: 1px solid #fed7d7;
        }
        
        .error-item:last-child {
            border-bottom: none;
        }
        
        .integration-card {
            background: white;
            border: 2px solid #e2e8f0;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 15px;
            transition: border-color 0.2s;
        }
        
        .integration-card:hover {
            border-color: #667eea;
        }
        
        .integration-name {
            font-size: 1.2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .integration-stats {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .stat {
            flex: 1;
            min-width: 120px;
        }
        
        .stat-label {
            font-size: 0.8em;
            color: #666;
        }
        
        .stat-value {
            font-size: 1.4em;
            font-weight: bold;
            color: #333;
        }
        
        footer {
            text-align: center;
            padding-top: 30px;
            margin-top: 40px;
            border-top: 2px solid #e2e8f0;
            color: #999;
            font-size: 0.9em;
        }
        
        .progress-bar {
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s;
        }
        """
    
    def _generate_overview_section(self, metrics: Dict[str, Any]) -> str:
        """Generate overview section with key metrics."""
        perf = metrics.get('performance', {})
        quality = metrics.get('quality', {})
        
        total_requests = perf.get('total_requests', 0)
        success_rate = perf.get('success_rate', 0.0) * 100
        avg_latency = perf.get('avg_latency_ms', 0.0) / 1000  # Convert to seconds
        avg_quality = quality.get('avg_score', 0.0)
        
        # Determine status based on metrics
        success_status = "status-good" if success_rate >= 90 else ("status-warning" if success_rate >= 75 else "status-error")
        latency_status = "status-good" if avg_latency < 5 else ("status-warning" if avg_latency < 10 else "status-error")
        quality_status = "status-good" if avg_quality >= 0.75 else ("status-warning" if avg_quality >= 0.6 else "status-error")
        
        return f"""
        <section id="overview">
            <h2>📊 Overview</h2>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-label">Total Requests</div>
                    <div class="metric-value">{total_requests}</div>
                </div>
                <div class="metric-card {success_status}">
                    <div class="metric-label">Success Rate</div>
                    <div class="metric-value">{success_rate:.1f}<span class="metric-unit">%</span></div>
                </div>
                <div class="metric-card {latency_status}">
                    <div class="metric-label">Avg Latency</div>
                    <div class="metric-value">{avg_latency:.2f}<span class="metric-unit">s</span></div>
                </div>
                <div class="metric-card {quality_status}">
                    <div class="metric-label">Avg Quality</div>
                    <div class="metric-value">{avg_quality:.3f}</div>
                </div>
            </div>
        </section>
        """
    
    def _generate_performance_section(self, metrics: Dict[str, Any]) -> str:
        """Generate performance metrics section."""
        perf = metrics.get('performance', {})
        
        return f"""
        <section id="performance">
            <h2>⚡ Performance Metrics</h2>
            <div class="chart-container">
                <canvas id="latencyChart"></canvas>
            </div>
            <div class="metric-grid">
                <div class="metric-card status-good">
                    <div class="metric-label">Total Tokens</div>
                    <div class="metric-value">{perf.get('total_tokens', 0):,}</div>
                </div>
                <div class="metric-card status-good">
                    <div class="metric-label">Avg Latency</div>
                    <div class="metric-value">{perf.get('avg_latency_ms', 0.0):.0f}<span class="metric-unit">ms</span></div>
                </div>
            </div>
        </section>
        """
    
    def _generate_quality_section(self, metrics: Dict[str, Any]) -> str:
        """Generate quality metrics section."""
        quality = metrics.get('quality', {})
        trend = quality.get('trend', [])
        
        return f"""
        <section id="quality">
            <h2>✨ Quality Metrics</h2>
            <div class="chart-container">
                <canvas id="qualityChart"></canvas>
            </div>
            <p style="color: #666; margin-top: 10px;">
                Current average quality score: <strong>{quality.get('avg_score', 0.0):.3f}</strong>
            </p>
        </section>
        """
    
    def _generate_reliability_section(self, metrics: Dict[str, Any]) -> str:
        """Generate reliability/error section."""
        perf = metrics.get('performance', {})
        errors = metrics.get('errors', {})
        
        error_rate = perf.get('error_rate', 0.0) * 100
        
        error_html = ""
        if errors:
            error_html = '<div class="error-list">'
            for error_type, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
                error_html += f'<div class="error-item"><strong>{error_type}</strong>: {count} occurrences</div>'
            error_html += '</div>'
        else:
            error_html = '<p style="color: #48bb78;">✅ No errors in this time window!</p>'
        
        return f"""
        <section id="reliability">
            <h2>🛡️ Reliability</h2>
            <div class="metric-grid">
                <div class="metric-card {'status-good' if error_rate < 5 else 'status-warning'}">
                    <div class="metric-label">Error Rate</div>
                    <div class="metric-value">{error_rate:.1f}<span class="metric-unit">%</span></div>
                </div>
            </div>
            <h3 style="margin: 20px 0 10px 0;">Error Breakdown</h3>
            {error_html}
        </section>
        """
    
    def _generate_integrations_section(self, metrics: Dict[str, Any]) -> str:
        """Generate integration-specific metrics."""
        integrations = metrics.get('integrations', {})
        
        if not integrations:
            return '<section id="integrations"><h2>🔧 Integrations</h2><p>No integration data available.</p></section>'
        
        cards_html = ""
        for integration, stats in sorted(integrations.items()):
            total = stats.get('total', 0)
            successful = stats.get('successful', 0)
            success_rate = (successful / total * 100) if total > 0 else 0
            
            cards_html += f"""
            <div class="integration-card">
                <div class="integration-name">{integration}</div>
                <div class="integration-stats">
                    <div class="stat">
                        <div class="stat-label">Requests</div>
                        <div class="stat-value">{total}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Success Rate</div>
                        <div class="stat-value">{success_rate:.1f}%</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Successful</div>
                        <div class="stat-value">{successful}</div>
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {success_rate}%"></div>
                </div>
            </div>
            """
        
        return f"""
        <section id="integrations">
            <h2>🔧 Integration Performance</h2>
            {cards_html}
        </section>
        """
    
    def _generate_backends_section(self, metrics: Dict[str, Any]) -> str:
        """Generate backend-specific metrics."""
        backends = metrics.get('backends', {})
        
        if not backends:
            return '<section id="backends"><h2>🌐 Backends</h2><p>No backend data available.</p></section>'
        
        cards_html = ""
        for backend, stats in sorted(backends.items()):
            count = stats.get('count', 0)
            avg_latency = stats.get('avg_latency', 0.0)
            
            cards_html += f"""
            <div class="integration-card">
                <div class="integration-name">{backend}</div>
                <div class="integration-stats">
                    <div class="stat">
                        <div class="stat-label">Requests</div>
                        <div class="stat-value">{count}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Avg Latency</div>
                        <div class="stat-value">{avg_latency:.0f}ms</div>
                    </div>
                </div>
            </div>
            """
        
        return f"""
        <section id="backends">
            <h2>🌐 Backend Performance</h2>
            {cards_html}
        </section>
        """
    
    def _generate_chart_scripts(self, metrics: Dict[str, Any]) -> str:
        """Generate JavaScript for charts."""
        quality = metrics.get('quality', {})
        quality_trend = quality.get('trend', [])
        
        # Generate labels for quality trend
        labels = [f"Point {i+1}" for i in range(len(quality_trend))]
        
        return f"""
        // Quality Trend Chart
        const qualityCtx = document.getElementById('qualityChart');
        if (qualityCtx) {{
            new Chart(qualityCtx, {{
                type: 'line',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [{{
                        label: 'Quality Score',
                        data: {json.dumps(quality_trend)},
                        borderColor: 'rgb(102, 126, 234)',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        tension: 0.4,
                        fill: true
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Quality Score Trend'
                        }},
                        legend: {{
                            display: false
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            max: 1.0,
                            ticks: {{
                                callback: function(value) {{
                                    return value.toFixed(2);
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        // Latency Chart (placeholder - would show backend latencies)
        const latencyCtx = document.getElementById('latencyChart');
        if (latencyCtx) {{
            const backends = {json.dumps(list(metrics.get('backends', {}).keys()))};
            const latencies = {json.dumps([stats.get('avg_latency', 0) for stats in metrics.get('backends', {}).values()])};
            
            new Chart(latencyCtx, {{
                type: 'bar',
                data: {{
                    labels: backends,
                    datasets: [{{
                        label: 'Avg Latency (ms)',
                        data: latencies,
                        backgroundColor: [
                            'rgba(102, 126, 234, 0.8)',
                            'rgba(118, 75, 162, 0.8)',
                            'rgba(72, 187, 120, 0.8)'
                        ],
                        borderColor: [
                            'rgb(102, 126, 234)',
                            'rgb(118, 75, 162)',
                            'rgb(72, 187, 120)'
                        ],
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Backend Latency Comparison'
                        }},
                        legend: {{
                            display: false
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{
                                callback: function(value) {{
                                    return value + ' ms';
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}
        """


if __name__ == "__main__":
    # Test dashboard generator
    print("Testing DashboardGenerator...")
    
    # Sample metrics
    test_metrics = {
        "time_window": "1h",
        "performance": {
            "total_requests": 247,
            "successful_requests": 233,
            "success_rate": 0.943,
            "error_rate": 0.057,
            "avg_latency_ms": 2450.0,
            "total_tokens": 125000
        },
        "quality": {
            "avg_score": 0.785,
            "trend": [0.72, 0.74, 0.76, 0.78, 0.79, 0.785]
        },
        "backends": {
            "groq": {"count": 150, "avg_latency": 1200.0},
            "openrouter": {"count": 85, "avg_latency": 3500.0},
            "local": {"count": 12, "avg_latency": 5800.0}
        },
        "integrations": {
            "parallel_generation": {"total": 45, "successful": 43},
            "multi_critic": {"total": 32, "successful": 30},
            "reflection": {"total": 28, "successful": 27}
        },
        "errors": {
            "timeout": 12,
            "rate_limit": 8,
            "api_error": 3
        }
    }
    
    generator = DashboardGenerator()
    html = generator.generate_dashboard(test_metrics)
    
    # Save test dashboard
    import os
    os.makedirs("data/metrics/dashboards", exist_ok=True)
    with open("data/metrics/dashboards/test_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ Dashboard generated: {len(html)} bytes")
    print("   Saved to: data/metrics/dashboards/test_dashboard.html")
    print("\n🎉 DashboardGenerator test complete!")
