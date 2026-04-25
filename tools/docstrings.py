import argparse
import os
import re
import urllib.request
from typing import Any

import jsonref
import libcst as cst
import libcst.matchers as m

CLS_ARG_MUTE = {"DataPackage" : ("resources", "profile")}

def extract_class_schemas(schema_node: dict | list, current_key: str = "DataPackage") -> dict:
    """
    Recursively maps object keys to their 'properties' dictionaries.
    Because jsonref handles $refs, we only need to worry about logical operators.
    """
    class_schemas = {}

    def merge_schemas(new_schemas: dict):
        for k, v in new_schemas.items():
            class_schemas.setdefault(k, {}).update(v)

    if isinstance(schema_node, list):
        for item in schema_node:
            merge_schemas(extract_class_schemas(item, current_key))
        return class_schemas

    if not isinstance(schema_node, dict):
        return class_schemas

    if "properties" in schema_node:
        key_lower = current_key.lower()
        merge_schemas({key_lower: schema_node["properties"]})
        
        if key_lower.endswith('s'):
            merge_schemas({key_lower[:-1]: schema_node["properties"]})
            
        for prop_name, prop_value in schema_node["properties"].items():
            merge_schemas(extract_class_schemas(prop_value, prop_name))

    for keyword in ["allOf", "anyOf", "oneOf", "items"]:
        if keyword in schema_node:
            merge_schemas(extract_class_schemas(schema_node[keyword], current_key))
            
    return class_schemas


class DocstringInjector(cst.CSTTransformer):
    """
    A LibCST Transformer that traverses the Python syntax tree, 
    identifies targeted classes, and injects/updates docstrings 
    based on the extracted JSON schema mapping.
    """
    def __init__(self, class_schemas: dict, target_classes: tuple[str, ...]):
        self.class_schemas = class_schemas
        self.target_classes = target_classes

    def _get_class_fields(self, body_node: cst.IndentedBlock) -> list[str]:
        """Extracts the names of all annotated assignment fields in the class."""
        fields = []
        for stmt in body_node.body:
            if m.matches(stmt, m.SimpleStatementLine(body=[m.AnnAssign()])):
                target = stmt.body[0].target
                if isinstance(target, cst.Name):
                    fields.append(target.value)
        return fields

    def _build_args_text(self, fields: list[str], schema_props: dict, skip : tuple[str, ...]=()) -> str:
        """Formats the 'Arguments:' section for the class docstring."""
        args_lines = []
        for field in fields:
            if field in skip:
                continue
            if field in schema_props:
                desc = schema_props[field].get("description") or schema_props[field].get("title", "")
                desc = desc or "Any."
                desc_clean = desc.strip().replace('\n', ' ')
                args_lines.append(f"        {field}: {desc_clean}")
                    
        if args_lines:
            return "\n\n    Arguments:\n" + "\n".join(args_lines) + "\n\n    "
        return ""

    def _update_class_docstring(self, body: list[cst.BaseStatement], args_text: str) -> list[cst.BaseStatement]:
        """Modifies or creates the class-level docstring to include the Arguments section."""
        new_body = list(body)
        
        if new_body and m.matches(new_body[0], m.SimpleStatementLine(body=[m.Expr(value=m.SimpleString())])):
            old_doc = new_body[0].body[0].value.value
            
            # Strip out existing 'Arguments:' section to avoid duplicates
            base_doc = re.split(r'\n\s*Arguments:', old_doc)[0]
            base_doc = re.sub(r'\s*"""$', '', base_doc)
            
            new_doc_str = f'{base_doc}{args_text}"""'
            new_doc_node = new_body[0].with_deep_changes(new_body[0].body[0].value, value=new_doc_str)
            new_body[0] = new_doc_node
            
        elif args_text:
            new_doc_str = f'"""{args_text}"""'
            new_doc_node = cst.SimpleStatementLine(body=[cst.Expr(value=cst.SimpleString(value=new_doc_str))])
            new_body.insert(0, new_doc_node)
            
        return new_body

    def _update_field_docstrings(self, body: list[cst.BaseStatement], schema_props: dict) -> list[cst.BaseStatement]:
        """Injects or updates docstrings immediately following field definitions."""
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
                            desc_clean = desc.strip().replace('\n', ' ')
                            doc_str = f'"""{desc_clean}"""'
                            doc_node = cst.SimpleStatementLine(body=[cst.Expr(value=cst.SimpleString(value=doc_str))])
                            
                            # Replace existing property docstring if it exists, otherwise insert
                            if i + 1 < len(body) and m.matches(body[i+1], m.SimpleStatementLine(body=[m.Expr(value=m.SimpleString())])):
                                final_body.append(doc_node)
                                i += 1  # Skip the old docstring node
                            else:
                                final_body.append(doc_node)
            i += 1
            
        return final_body

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        """Orchestrates the docstring injection process for a targeted class."""
        class_name = original_node.name.value
        
        if class_name not in self.target_classes:
            return updated_node
        
        # Get fields to omit from "Arguments" section of class docstring
        arg_mute = CLS_ARG_MUTE.get(class_name, tuple())
            
        class_key = class_name.lower()
        schema_props = self.class_schemas.get(class_key, {})
        fields = self._get_class_fields(updated_node.body)
        args_text = self._build_args_text(fields, schema_props, arg_mute)
        body_with_class_doc = self._update_class_docstring(list(updated_node.body.body), args_text)
        final_body = self._update_field_docstrings(body_with_class_doc, schema_props)

        return updated_node.with_deep_changes(updated_node.body, body=final_body)


def add_docstrings_from_schema(source_file: str, output_file: str, classes: tuple[str, ...]):
    """
    Orchestrates fetching the schema via jsonref, parsing the code into a CST, 
    running the transformer, and saving the updated module.
    """
    schema_url = "https://raw.githubusercontent.com/tdwg/camtrap-dp/refs/heads/main/camtrap-dp-profile.json"
    
    with urllib.request.urlopen(schema_url) as response:
        schema = jsonref.loads(response.read().decode())
    
    class_schemas = extract_class_schemas(schema)

    with open(source_file, "r") as f:
        source_code = f.read()

    module = cst.parse_module(source_code)
    transformer = DocstringInjector(class_schemas, target_classes=classes)
    modified_module = module.visit(transformer)

    with open(output_file, "w") as f:
        f.write(modified_module.code)
        
    print(f"Successfully generated docstrings in {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Update docstrings dynamically based on the Camtrap DP datapackage standard."
    )
    parser.add_argument(
        "-i", "--input", type=str, default="src/trap_schema",
        help="Path to the directory containing the implementation of the Camtrap DP datapackage standard."
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None,
        help="Path to the directory where the updated files should be created. By default the same as input is used."
    )
    parser.add_argument(
        "-c", "--classes", type=str, nargs="+", 
        default=["Resource", "Contributor", "Source", "License", "Project", "Temporal", "Taxonomic", "RelatedIdentifiers", "DataPackage"],
        help="List of Python class names to update."
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

    add_docstrings_from_schema(
        os.path.join(src_dir, "datapackage.py"), 
        os.path.join(out_dir, "datapackage.py"),
        classes=tuple(args.classes)
    )

if __name__ == "__main__":
    main()