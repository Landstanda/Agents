from typing import Dict, Any, List
import json
from pathlib import Path
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger

logger = get_logger(__name__)

class ReportGeneratorModule(BaseModule):
    """Module for generating reports from processed data"""
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a report from input data
        
        Expected params:
        - data: Dict[str, Any] - Data to include in report
        - format: str - Output format (json/txt/html)
        - output_path: str - Where to save the report
        
        Returns:
        - report_path: str - Path to generated report
        """
        try:
            data = params['data']
            format = params.get('format', 'json')
            output_path = Path(params['output_path'])
            
            # Create output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == 'json':
                with open(output_path, 'w') as f:
                    json.dump(data, f, indent=2)
            elif format == 'txt':
                with open(output_path, 'w') as f:
                    self._write_txt_report(data, f)
            elif format == 'html':
                with open(output_path, 'w') as f:
                    self._write_html_report(data, f)
            
            return {
                'report_path': str(output_path),
                'format': format
            }
            
        except Exception as e:
            logger.error(f"Report generation error: {str(e)}")
            raise
    
    def _write_txt_report(self, data: Dict, file):
        """Write report in text format"""
        def _format_dict(d, indent=0):
            lines = []
            for k, v in d.items():
                if isinstance(v, dict):
                    lines.append("  " * indent + f"{k}:")
                    lines.extend(_format_dict(v, indent + 1))
                else:
                    lines.append("  " * indent + f"{k}: {v}")
            return lines
        
        file.write("\n".join(_format_dict(data)))
    
    def _write_html_report(self, data: Dict, file):
        """Write report in HTML format"""
        html = ["<html><body><div class='report'>"]
        
        def _format_dict(d):
            elements = ["<dl>"]
            for k, v in d.items():
                elements.append(f"<dt>{k}</dt>")
                if isinstance(v, dict):
                    elements.append(f"<dd>{_format_dict(v)}</dd>")
                else:
                    elements.append(f"<dd>{v}</dd>")
            elements.append("</dl>")
            return "\n".join(elements)
        
        html.append(_format_dict(data))
        html.append("</div></body></html>")
        file.write("\n".join(html))
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        return (
            isinstance(params.get('data'), dict) and
            isinstance(params.get('output_path'), str) and
            params.get('format', 'json') in ['json', 'txt', 'html']
        )
    
    @property
    def capabilities(self) -> List[str]:
        return ['report_generation', 'file_output', 'data_formatting'] 