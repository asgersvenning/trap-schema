import argparse
import os
import urllib.request
from textwrap import wrap
from typing import Any, Literal

import jsonref
import libcst as cst
import libcst.matchers as m
from frictionless import Schema

PROFILE_URL = "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/camtrap-dp-profile.json"
DEPLOYMENTS_URL = "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/deployments-table-schema.json"
MEDIA_URL = "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/media-table-schema.json"
OBSERVATIONS_URL = "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/observations-table-schema.json"

CLS_ARG_MUTE = {"DataPackage": ("resources", "profile")}


def format_text(text: str, indent: str) -> str:
    return "\n".join(wrap(text, width=100, subsequent_indent=indent))


def extract_profile_schemas(schema_node: dict | list, current_key: str = "DataPackage") -> dict:
    """Recursively maps object keys to their 'properties' dictionaries from a JSON Profile."""
    class_schemas = {}

    def merge_schemas(new_schemas: dict):
        for k, v in new_schemas.items():
            if k not in class_schemas:
                class_schemas[k] = {"__description__": "", "properties": {}, "__doc_header__": "Arguments:"}
            class_schemas[k]["properties"].update(v.get("properties", {}))
            
            if v.get("__description__") and not class_schemas[k]["__description__"]:
                class_schemas[k]["__description__"] = v["__description__"]

    if isinstance(schema_node, list):
        for item in schema_node:
            merge_schemas(extract_profile_schemas(item, current_key))
        return class_schemas

    if not isinstance(schema_node, dict):
        return class_schemas

    if "properties" in schema_node:
        key_lower = current_key.lower()
        desc = schema_node.get("description") or schema_node.get("title") or ""
        
        base_schema = {"__description__": desc, "properties": schema_node["properties"], "__doc_header__": "Arguments:"}
        
        merge_schemas({key_lower: base_schema})
        if key_lower.endswith('s'):
            merge_schemas({key_lower[:-1]: base_schema})
            
        for prop_name, prop_value in schema_node["properties"].items():
            merge_schemas(extract_profile_schemas(prop_value, prop_name))

    for keyword in ["allOf", "anyOf", "oneOf", "items"]:
        if keyword in schema_node:
            merge_schemas(extract_profile_schemas(schema_node[keyword], current_key))
            
    return class_schemas


def fetch_json_schema(url: str) -> dict:
    """Fetches a JSON schema, resolves $refs, and extracts the profile mapping."""
    with urllib.request.urlopen(url) as response:
        profile_schema = jsonref.loads(response.read().decode())
    return extract_profile_schemas(profile_schema)


def fetch_table_schema(urls: dict[str, str]) -> dict:
    """Uses Frictionless to parse multiple Table Schemas and map them to Row/Table classes."""
    class_schemas = {}
    for base_name, url in urls.items():
        schema = Schema(url)
        props = {}
        for field in schema.fields:
            props[field.name] = {
                "description": field.description or field.title or ""
            }
        
        desc = schema.description or schema.title or ""
        
        class_schemas[f"{base_name}Row".lower()] = {
            "__description__": desc,
            "properties": props,
            "__doc_header__": "Arguments:"
        }
        
        class_schemas[f"{base_name}Table".lower()] = {
            "__description__": desc,
            "properties": props,
            "__doc_header__": "Attributes:"
        }
        
    return class_schemas


def get_fetcher(schema_type: str):
    match schema_type:
        case "jsonschema":
            return fetch_json_schema
        case "frictionless-table-schema":
            return fetch_table_schema
        case _:
            raise ValueError(f"Unknown schema_type: {schema_type}")


class DocstringInjector(cst.CSTTransformer):
    """
    A LibCST Transformer that traverses the Python syntax tree, identifies 
    targeted classes, and completely standardizes docstrings based on external schemas.
    """
    def __init__(self, class_schemas: dict, target_classes: tuple[str, ...]):
        self.class_schemas = class_schemas
        self.target_classes = target_classes

    def _get_class_fields(self, body_node: cst.IndentedBlock) -> list[str]:
        fields = []
        for stmt in body_node.body:
            if m.matches(stmt, m.SimpleStatementLine(body=[m.AnnAssign()])):
                target = stmt.body[0].target
                if isinstance(target, cst.Name):
                    fields.append(target.value)
        return fields

    def _build_args_text(self, ast_fields: list[str], schema_info: dict, skip: tuple[str, ...]=(), is_table: bool=False) -> str:
        properties = schema_info.get("properties", {})
        header = schema_info.get("__doc_header__", "Arguments:")
        
        fields_to_doc = list(properties.keys()) if is_table else ast_fields
            
        args_lines = []
        for field in fields_to_doc:
            if field in skip:
                continue
            if field in properties:
                desc = properties[field].get("description") or properties[field].get("title", "")
                desc = desc or "Any."
                desc_clean = format_text(desc, "            ")
                args_lines.append(f"        {field}: {desc_clean}")
                
        if args_lines:
            return f"\n\n    {header}\n" + "\n".join(args_lines) + "\n\n    "
        return ""

    def _update_class_docstring(self, body: list[cst.BaseStatement], class_desc: str, args_text: str) -> list[cst.BaseStatement]:
        new_body = list(body)
        class_desc_formatted = format_text(class_desc, "    ") if class_desc else ""
        
        full_text = ""
        if class_desc_formatted:
            full_text += class_desc_formatted
        if args_text:
            full_text += args_text
            
        if not full_text:
            return new_body
            
        new_doc_str = f'"""{full_text}"""'
        
        if new_body and m.matches(new_body[0], m.SimpleStatementLine(body=[m.Expr(value=m.SimpleString())])):
            new_doc_node = new_body[0].with_deep_changes(new_body[0].body[0].value, value=new_doc_str)
            new_body[0] = new_doc_node
        else:
            new_doc_node = cst.SimpleStatementLine(body=[cst.Expr(value=cst.SimpleString(value=new_doc_str))])
            new_body.insert(0, new_doc_node)
            
        return new_body

    def _update_field_docstrings(self, body: list[cst.BaseStatement], schema_props: dict) -> list[cst.BaseStatement]:
        final_body = []
        i = 0
        
        while i < len(body):
            stmt = body[i]
            final_body.append(stmt)
            
            if m.matches(stmt, m.SimpleStatementLine(body=[m.AnnAssign()])):
                target = stmt.body[0].target
                
                if isinstance(target, cst.Name):
                    field_name = target.value
                    
                    if field_name in schema_props:
                        desc = schema_props[field_name].get("description") or schema_props[field_name].get("title", "")
                        
                        if desc:
                            desc_clean = format_text(desc, "    ")
                            doc_str = f'"""{desc_clean}"""'
                            doc_node = cst.SimpleStatementLine(body=[cst.Expr(value=cst.SimpleString(value=doc_str))])
                            
                            if i + 1 < len(body) and m.matches(body[i+1], m.SimpleStatementLine(body=[m.Expr(value=m.SimpleString())])):
                                final_body.append(doc_node)
                                i += 1  
                            else:
                                final_body.append(doc_node)
            i += 1
            
        return final_body

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        class_name = original_node.name.value
        
        if class_name not in self.target_classes:
            return updated_node
        
        arg_mute = CLS_ARG_MUTE.get(class_name, tuple())
        class_key = class_name.lower()
        schema_info = self.class_schemas.get(class_key, {})
        
        is_table = class_name.endswith("Table")
        
        ast_fields = self._get_class_fields(updated_node.body)
        args_text = self._build_args_text(ast_fields, schema_info, arg_mute, is_table)
        
        class_desc = schema_info.get("__description__", "")
        body_with_class_doc = self._update_class_docstring(list(updated_node.body.body), class_desc, args_text)
        
        final_body = self._update_field_docstrings(body_with_class_doc, schema_info.get("properties", {}))

        return updated_node.with_deep_changes(updated_node.body, body=final_body)


def process_file(
    schema_urls: str | dict[str, str], 
    schema_type: Literal["jsonschema", "frictionless-table-schema"],
    source_file: str, 
    output_file: str,
    classes: tuple[str, ...]
):
    if not os.path.exists(source_file):
        print(f"Skipping {source_file}: file not found.")
        return

    schema = get_fetcher(schema_type)(schema_urls)

    with open(source_file, encoding="utf-8") as f:
        source_code = f.read()

    module = cst.parse_module(source_code)
    transformer = DocstringInjector(schema, target_classes=classes)
    modified_module = module.visit(transformer)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(modified_module.code)
        
    print(f"Successfully synced docstrings in {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Syncs Python class docstrings with Camtrap DP and Frictionless Data standards."
    )
    parser.add_argument(
        "-i", "--input", type=str, default="src/trap_schema",
        help="Path to the directory containing the schemas."
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None,
        help="Path to the output directory. Overwrites input if omitted."
    )

    args, extra = parser.parse_known_args()
    if extra:
        raise KeyError(f'Unknown arguments: {extra}')
        
    src_dir: str | Any = args.input
    if (
        not isinstance(src_dir, str) or 
        not os.path.exists(src_dir := os.sep.join(src_dir.split("/"))) or 
        not os.path.isdir(src_dir)
    ):
        raise NotADirectoryError(f'Input directory {src_dir} is not a valid existing directory.')
        
    out_dir = args.output or src_dir
    os.makedirs(out_dir, exist_ok=True)

    # 1. Sync the Profile Schema to datapackage.py
    process_file(
        schema_urls=PROFILE_URL,
        schema_type="jsonschema",
        source_file=os.path.join(src_dir, "datapackage.py"),
        output_file=os.path.join(out_dir, "datapackage.py"),
        classes=("Resource", "Contributor", "Source", "License", "Project", "Temporal", "Taxonomic", "RelatedIdentifiers", "DataPackage")
    )

    # 2. Sync Frictionless Table Schemas to tables.py
    process_file(
        schema_urls={
            "Deployment": DEPLOYMENTS_URL,
            "Media": MEDIA_URL,
            "Observations": OBSERVATIONS_URL
        },
        schema_type="frictionless-table-schema",
        source_file=os.path.join(src_dir, "tables.py"),
        output_file=os.path.join(out_dir, "tables.py"),
        classes=(
            "DeploymentRow", "MediaRow", "ObservationsRow",
            "DeploymentTable", "MediaTable", "ObservationsTable"
        )
    )

if __name__ == "__main__":
    main()