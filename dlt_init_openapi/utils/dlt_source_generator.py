"""
dlt Source Generator for OpenAPI endpoints.

Generates @dlt.source decorated functions that can be directly used with dlt pipelines.
Each function makes actual HTTP requests and returns data ready for loading.
"""

from typing import List, Optional, Any, Dict
from dataclasses import dataclass

from dlt_init_openapi.utils.misc import snake_case, fix_reserved_words


@dataclass
class SourceParameter:
    """Represents a parameter for a dlt source function"""
    name: str
    type_hint: str
    required: bool
    default_value: Optional[str] = None
    description: Optional[str] = None
    location: str = "query"  # query, path, header, body


class DltSourceGenerator:
    """
    Generates dlt @dlt.source decorated functions from OpenAPI endpoints.
    
    Each endpoint becomes a standalone dlt source that can be loaded into a pipeline.
    """
    
    # Type mapping from OpenAPI types to Python types
    TYPE_MAP = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "object": "dict",
        "array": "list",
    }
    
    def generate_dlt_source(
        self,
        endpoint_name: str,
        method: str,
        path: str,
        parameters: List[SourceParameter],
        description: Optional[str] = None,
        base_url: str = "BASE_URL"
    ) -> str:
        """
        Generate a complete @dlt.source decorated function with actual HTTP implementation.
        
        Args:
            endpoint_name: Name of the function (e.g., 'get_users', 'create_user')
            method: HTTP method (GET, POST, PUT, PATCH, DELETE, etc.)
            path: API path (e.g., '/users/{id}')
            parameters: List of parameters (path, query, header, body)
            description: Optional endpoint description from OpenAPI
            base_url: Variable name for the base URL
            
        Returns:
            Complete Python function as string with @dlt.source decorator
        """
        func_name = fix_reserved_words(snake_case(endpoint_name))
        
        # Separate parameters by location
        path_params = [p for p in parameters if p.location == "path"]
        query_params = [p for p in parameters if p.location == "query"]
        header_params = [p for p in parameters if p.location == "header"]
        body_params = [p for p in parameters if p.location == "body"]
        
        # Build function signature
        required_params = [p for p in parameters if p.required]
        optional_params = [p for p in parameters if not p.required]
        
        # Decorator
        decorator = "@dlt.source"
        
        # Function signature
        sig_parts = [f"def {func_name}("]
        param_lines = []
        
        for param in required_params:
            param_name = fix_reserved_words(snake_case(param.name))
            param_lines.append(f"    {param_name}: {param.type_hint}")
        
        for param in optional_params:
            param_name = fix_reserved_words(snake_case(param.name))
            default = param.default_value or "None"
            param_lines.append(f"    {param_name}: Optional[{param.type_hint}] = {default}")
        
        if param_lines:
            sig_parts.append(",\n".join(param_lines))
        
        sig_parts.append("):")
        signature = "".join(sig_parts)
        
        # Docstring
        docstring_parts = ['    """']
        if description:
            docstring_parts.append(f"    {description}")
            docstring_parts.append("")
        docstring_parts.append(f"    {method} {path}")
        
        if parameters:
            docstring_parts.append("")
            docstring_parts.append("    Args:")
            for param in parameters:
                param_name = fix_reserved_words(snake_case(param.name))
                req_str = "required" if param.required else "optional"
                desc = f" - {param.description}" if param.description else ""
                docstring_parts.append(f"        {param_name}: {req_str}{desc}")
        
        docstring_parts.append("")
        docstring_parts.append("    Returns:")
        docstring_parts.append("        API response data ready for dlt pipeline")
        docstring_parts.append('    """')
        docstring = "\n".join(docstring_parts)
        
        # Function body
        body_lines = []
        
        # URL construction
        if path_params:
            body_lines.append(f'    url = f"{{{base_url}}}{path}"')
            for param in path_params:
                param_name = fix_reserved_words(snake_case(param.name))
                body_lines.append(f"    url = url.replace('{{{param.name}}}', str({param_name}))")
        else:
            body_lines.append(f'    url = f"{{{base_url}}}{path}"')
        
        body_lines.append("")
        
        # Headers
        if header_params:
            body_lines.append("    headers = {")
            for param in header_params:
                param_name = fix_reserved_words(snake_case(param.name))
                if param.required:
                    body_lines.append(f'        "{param.name}": str({param_name}),')
                else:
                    body_lines.append(f'        **({{"' + param.name + f'": str({param_name})}} if {param_name} is not None else {{}}),')
            body_lines.append("    }")
        else:
            body_lines.append("    headers = {}")
        
        body_lines.append("")
        
        # Query parameters
        if query_params:
            body_lines.append("    params = {")
            for param in query_params:
                param_name = fix_reserved_words(snake_case(param.name))
                if param.required:
                    body_lines.append(f'        "{param.name}": {param_name},')
                else:
                    body_lines.append(f'        **({{"' + param.name + f'": {param_name}}} if {param_name} is not None else {{}}),')
            body_lines.append("    }")
        else:
            body_lines.append("    params = None")
        
        body_lines.append("")
        
        # Request body
        if body_params:
            body_lines.append("    json_data = {")
            for param in body_params:
                param_name = fix_reserved_words(snake_case(param.name))
                if param.required:
                    body_lines.append(f'        "{param.name}": {param_name},')
                else:
                    body_lines.append(f'        **({{"' + param.name + f'": {param_name}}} if {param_name} is not None else {{}}),')
            body_lines.append("    }")
        else:
            body_lines.append("    json_data = None")
        
        body_lines.append("")
        
        # HTTP request
        body_lines.append("    response = requests.request(")
        body_lines.append(f'        method="{method}",')
        body_lines.append("        url=url,")
        body_lines.append("        headers=headers,")
        body_lines.append("        params=params,")
        body_lines.append("        json=json_data,")
        body_lines.append("    )")
        body_lines.append("    response.raise_for_status()")
        body_lines.append("")
        body_lines.append("    if response.content:")
        body_lines.append("        return response.json()")
        body_lines.append("    return {}")
        
        body = "\n".join(body_lines)
        
        return f"{decorator}\n{signature}\n{docstring}\n{body}\n"
    
    def extract_parameters_from_endpoint(self, endpoint: Any) -> List[SourceParameter]:
        """Extract all parameters from an endpoint object."""
        params = []
        
        # Path, query, header parameters
        for param_name, param in endpoint.parameters.items():
            type_hint = self._convert_schema_to_type(param.schema)
            
            params.append(SourceParameter(
                name=param.name,
                type_hint=type_hint,
                required=param.required,
                default_value=self._get_default_value(param),
                description=param.description,
                location=param.location
            ))
        
        # Request body parameters
        if endpoint.request_body_params:
            for body_param in endpoint.request_body_params:
                params.extend(self._flatten_body_param(body_param))
        
        return params
    
    def _flatten_body_param(self, body_param: Any, prefix: str = "") -> List[SourceParameter]:
        """Flatten nested body parameters."""
        params = []
        param_name = f"{prefix}{body_param.name}" if prefix else body_param.name
        
        if body_param.nested_properties:
            for nested in body_param.nested_properties:
                params.extend(self._flatten_body_param(nested, prefix=f"{param_name}_"))
        else:
            type_hint = self._get_python_type(body_param.type, body_param.format)
            params.append(SourceParameter(
                name=param_name,
                type_hint=type_hint,
                required=body_param.required,
                default_value=self._format_default(body_param.default),
                description=body_param.description,
                location="body"
            ))
        
        return params
    
    def _convert_schema_to_type(self, schema: Any) -> str:
        """Convert SchemaWrapper to Python type hint."""
        if not schema.types:
            return "Any"
        
        primary_type = schema.types[0]
        py_type = self._get_python_type(primary_type, schema.type_format)
        
        if primary_type == "array" and schema.array_item:
            item_type = self._convert_schema_to_type(schema.array_item)
            return f"List[{item_type}]"
        
        return py_type
    
    def _get_python_type(self, openapi_type: str, format_hint: Optional[str] = None) -> str:
        """Convert OpenAPI type to Python type."""
        return self.TYPE_MAP.get(openapi_type, "Any")
    
    def _get_default_value(self, param: Any) -> Optional[str]:
        """Get default value for parameter."""
        if param.default is not None:
            return self._format_default(param.default)
        return None
    
    def _format_default(self, value: Any) -> str:
        """Format default value for Python code."""
        if value is None:
            return "None"
        elif isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return str(value)
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            return repr(value)
    
    def generate_all_sources(self, endpoints: List[Any], base_url: str = None) -> str:
        """
        Generate complete module with all dlt sources.
        
        Args:
            endpoints: List of Endpoint objects from OpenAPI parser
            base_url: Base URL from OpenAPI spec servers
            
        Returns:
            Complete Python module with all @dlt.source functions
        """
        lines = []
        
        # Extract base URL
        if base_url is None and endpoints:
            if hasattr(endpoints[0], 'context'):
                servers = endpoints[0].context.spec.servers
                if servers and servers[0].url:
                    base_url = servers[0].url
        
        # Module header
        lines.append('"""')
        lines.append("Auto-generated dlt sources from OpenAPI specification.")
        lines.append("")
        lines.append("Each function is a @dlt.source that can be loaded into a dlt pipeline.")
        lines.append('"""')
        lines.append("")
        lines.append("import dlt")
        lines.append("import requests")
        lines.append("from typing import Optional, List, Dict, Any")
        lines.append("")
        lines.append("")
        
        # Base URL
        if base_url and base_url != "/":
            lines.append(f'BASE_URL = "{base_url}"')
        else:
            lines.append('BASE_URL = "https://api.example.com"  # TODO: Set your API base URL')
        
        lines.append("")
        lines.append("")
        
        # Generate each source
        for endpoint in endpoints:
            params = self.extract_parameters_from_endpoint(endpoint)
            func_name = endpoint.detected_resource_name or endpoint.operation_id
            
            source_code = self.generate_dlt_source(
                endpoint_name=func_name,
                method=endpoint.method,
                path=endpoint.path,
                parameters=params,
                description=endpoint.description or endpoint.summary,
                base_url="BASE_URL"
            )
            lines.append(source_code)
            lines.append("")
        
        return "\n".join(lines)