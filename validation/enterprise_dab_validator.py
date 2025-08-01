#!/usr/bin/env python3
"""
Enterprise Databricks Asset Bundle (DAB) Configuration Validator

This validator enforces enterprise-specific policy validations that complement
the built-in `dab validate` command. It validates organizational compliance
requirements including variable usage, naming conventions, required tagging,
security policies, and operational best practices.

Prerequisites:
- Run the built-in `dab validate` command first to ensure basic DAB validity
- Ensure all required variables are defined in databricks.yml

Usage:
    python enterprise_dab_validator.py [--path PROJECT_PATH] [--strict]
"""

import os
import re
import sys
import argparse
import yaml
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, TextIO
from datetime import datetime

class EnterpriseDabValidator:
    """
    Enterprise policy validator for Databricks Asset Bundle configurations.
    
    This class validates DAB configurations against enterprise policies and
    best practices, categorizing findings into errors (must fix), warnings
    (should fix), and suggestions (consider implementing).
    """

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path)
        self.databricks_yaml = self.project_path / "databricks.yml"
        self.jobs_dir = self.project_path / "resources"
        
        # Categorized validation results
        self.errors = []      # Critical policy violations (exit code 1)
        self.warnings = []    # Important recommendations (exit code 1 with --strict)
        self.suggestions = [] # Optimization opportunities (informational only)
        
        # Enterprise policies
        self.required_tags = {"cost_center", "environment", "team"}
        self.sensitive_fields = {
            "existing_cluster_id", "instance_pool_id", "warehouse_id",
            "catalog", "schema", "volume", "storage_location"
        }
        self.security_patterns = [
            r"password[s]?\s*[:=]\s*['\"][^'\"]+['\"]",
            r"secret[s]?\s*[:=]\s*['\"][^'\"]+['\"]",
            r"token[s]?\s*[:=]\s*['\"][^'\"]+['\"]",
            r"key[s]?\s*[:=]\s*['\"][^'\"]+['\"]"
        ]

    def load_yaml(self, file_path: Path) -> Dict:
        """Load YAML file safely."""
        try:
            with open(file_path, "r") as file:
                return yaml.safe_load(file) or {}
        except Exception as e:
            self.errors.append(f"Failed to load {file_path}: {str(e)}")
            return {}

    def extract_environment_variables(self) -> Dict[str, Dict]:
        """Extract variables from each target and global variables in databricks.yml."""
        config = self.load_yaml(self.databricks_yaml)
        if not config:
            return {}
            
        # Get global variables
        global_variables = config.get("variables", {})
        
        targets = config.get("targets", {})
        env_variables = {}
        
        # Add global variables to each target
        for target_name, target_config in targets.items():
            target_variables = target_config.get("variables", {})
            # Merge global and target-specific variables (target-specific override global)
            merged_variables = {**global_variables, **target_variables}
            env_variables[target_name] = merged_variables
            
        # If no targets, just return global variables
        if not env_variables and global_variables:
            env_variables["global"] = global_variables
            
        return env_variables

    def check_variable_usage_policy(self, job_config: Dict, file_path: str) -> None:
        """Check if sensitive fields use variables instead of hardcoded values."""
        def check_object(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    # Check if sensitive field uses variables
                    if key in self.sensitive_fields:
                        if isinstance(value, str) and not value.startswith("${"):
                            self.errors.append(
                                f"Policy violation: '{current_path}' in {file_path} must use variables, "
                                f"not hardcoded value '{value}'"
                            )
                    
                    check_object(value, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_object(item, f"{path}[{i}]")
        
        check_object(job_config)

    def check_naming_conventions(self, job_config: Dict, file_path: str) -> None:
        """Check enterprise naming conventions."""
        jobs = job_config.get("resources", {}).get("jobs", {})
        
        for job_name, job_def in jobs.items():
            # Job names should start with capital letter and include environment
            if not re.match(r'^[A-Z][a-zA-Z0-9_]*', job_name):
                self.warnings.append(
                    f"Naming convention: Job '{job_name}' in {file_path} should start with capital letter"
                )
            
            # Should include environment reference
            if "${bundle.environment}" not in str(job_def.get("name", "")):
                self.warnings.append(
                    f"Best practice: Job '{job_name}' name should include environment reference"
                )
            
            # Check job cluster naming
            for cluster in job_def.get("job_clusters", []):
                cluster_key = cluster.get("job_cluster_key", "")
                if cluster_key and not re.match(r'^[a-z][a-z0-9_]*$', cluster_key):
                    self.warnings.append(
                        f"Naming convention: Job cluster key '{cluster_key}' should use lowercase with underscores"
                    )

    def check_required_tags(self, job_config: Dict, file_path: str) -> None:
        """Check if required enterprise tags are present."""
        jobs = job_config.get("resources", {}).get("jobs", {})
        
        for job_name, job_def in jobs.items():
            # Check job-level tags first
            tags = job_def.get("tags", {})
            
            # Also check cluster-level custom_tags
            for cluster in job_def.get("job_clusters", []):
                cluster_tags = cluster.get("new_cluster", {}).get("custom_tags", {})
                tags.update(cluster_tags)
            
            missing_tags = self.required_tags - set(tags.keys())
            
            if missing_tags:
                self.errors.append(
                    f"Policy violation: Job '{job_name}' in {file_path} missing required tags: {missing_tags}"
                )

    def check_security_compliance(self, job_config: Dict, file_path: str) -> None:
        """Check for security compliance issues."""
        job_str = yaml.dump(job_config)
        
        # Check for hardcoded secrets
        for pattern in self.security_patterns:
            if re.search(pattern, job_str, re.IGNORECASE):
                self.errors.append(
                    f"Security violation: Potential hardcoded secret found in {file_path}"
                )
        
        # Check for suspicious notebook paths
        jobs = job_config.get("resources", {}).get("jobs", {})
        for job_name, job_def in jobs.items():
            for task in job_def.get("tasks", []):
                notebook_task = task.get("notebook_task", {})
                notebook_path = notebook_task.get("notebook_path", "")
                
                if "/tmp/" in notebook_path or "/personal/" in notebook_path:
                    self.warnings.append(
                        f"Security concern: Notebook path '{notebook_path}' in job '{job_name}' "
                        f"uses non-standard location"
                    )
            
            # Check max concurrent runs
            max_concurrent = job_def.get("max_concurrent_runs", 1)
            if max_concurrent > 5:
                self.warnings.append(
                    f"Security policy: Job '{job_name}' max_concurrent_runs ({max_concurrent}) "
                    f"exceeds recommended limit of 5"
                )

    def check_cost_optimization(self, job_config: Dict, file_path: str) -> None:
        """Analyze configurations for cost optimization opportunities."""
        jobs = job_config.get("resources", {}).get("jobs", {})
        
        for job_name, job_def in jobs.items():
            # Check for excessive worker counts
            for cluster in job_def.get("job_clusters", []):
                new_cluster = cluster.get("new_cluster", {})
                num_workers = new_cluster.get("num_workers")
                
                if isinstance(num_workers, (int, str)) and str(num_workers).isdigit():
                    if int(num_workers) > 10:
                        self.suggestions.append(
                            f"Cost optimization: Job '{job_name}' cluster has {num_workers} workers. "
                            f"Consider if this is necessary for your workload."
                        )
                
                # Suggest using variables for node types
                node_type = new_cluster.get("node_type_id")
                if isinstance(node_type, str) and not node_type.startswith("${"):
                    self.suggestions.append(
                        f"Cost optimization: Job '{job_name}' uses hardcoded node_type_id. "
                        f"Consider using variables for easier cost management across environments."
                    )

    def check_best_practices(self, job_config: Dict, file_path: str) -> None:
        """Check enterprise best practices."""
        jobs = job_config.get("resources", {}).get("jobs", {})
        
        for job_name, job_def in jobs.items():
            # Should have email notifications
            email_notifications = job_def.get("email_notifications", {})
            if not email_notifications.get("on_failure"):
                self.suggestions.append(
                    f"Best practice: Job '{job_name}' should have email notifications for failures"
                )
            
            # Should have timeout configured
            if "timeout_seconds" not in job_def:
                self.suggestions.append(
                    f"Best practice: Job '{job_name}' should have timeout_seconds configured"
                )
            
            # Should have retry configuration for production jobs
            if "retry_on_timeout" not in job_def:
                self.suggestions.append(
                    f"Best practice: Job '{job_name}' should consider retry_on_timeout configuration"
                )

    def validate_environment_consistency(self) -> None:
        """Check that variables are consistently defined across environments."""
        env_variables = self.extract_environment_variables()
        
        if len(env_variables) < 2:
            return  # Need at least 2 environments to compare
        
        # Get all variable names from all environments
        all_var_names = set()
        for env_vars in env_variables.values():
            all_var_names.update(env_vars.keys())
        
        # Check each variable exists in all environments
        for var_name in all_var_names:
            missing_envs = []
            for env_name, env_vars in env_variables.items():
                if var_name not in env_vars:
                    missing_envs.append(env_name)
            
            if missing_envs:
                self.warnings.append(
                    f"Environment consistency: Variable '{var_name}' missing in environments: {missing_envs}"
                )

    def validate_job_file(self, job_file: Path) -> None:
        """Validate a single job configuration file."""
        job_config = self.load_yaml(job_file)
        if not job_config:
            return
            
        file_path = str(job_file.relative_to(self.project_path))
        
        # Run all enterprise policy checks
        self.check_variable_usage_policy(job_config, file_path)
        self.check_naming_conventions(job_config, file_path)
        self.check_required_tags(job_config, file_path)
        self.check_security_compliance(job_config, file_path)
        self.check_cost_optimization(job_config, file_path)
        self.check_best_practices(job_config, file_path)

    def validate(self) -> bool:
        """Run all enterprise validations."""
        print("=" * 80)
        print("ENTERPRISE DATABRICKS ASSET BUNDLE (DAB) POLICY VALIDATOR")
        print("=" * 80)
        print("Running enterprise-specific policy validations...")
        print("(Complementing built-in 'dab validate' with organizational compliance checks)")
        print("-" * 80)
        
        # Validate environment consistency
        self.validate_environment_consistency()
        
        # Validate job files
        if self.jobs_dir.exists():
            job_files = list(self.jobs_dir.glob("**/*.yaml")) + list(self.jobs_dir.glob("**/*.yml"))
            for job_file in job_files:
                self.validate_job_file(job_file)
        
        return len(self.errors) == 0

    def _write_output(self, message: str, file_handle: Optional[TextIO] = None) -> None:
        """Write output to console and optionally to file."""
        print(message)
        if file_handle:
            file_handle.write(message + "\n")

    def print_results(self, output_file: Optional[str] = None) -> None:
        """Print categorized validation results to console and optionally to file."""
        total_issues = len(self.errors) + len(self.warnings) + len(self.suggestions)
        
        file_handle = None
        if output_file:
            try:
                file_handle = open(output_file, 'w', encoding='utf-8')
                # Write header with timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                file_handle.write(f"# Enterprise DAB Validation Report\n")
                file_handle.write(f"# Generated: {timestamp}\n")
                file_handle.write(f"# Project Path: {self.project_path}\n\n")
            except Exception as e:
                print(f"Warning: Could not create output file '{output_file}': {e}")
                file_handle = None
        
        try:
            self._write_output("\n" + "=" * 80, file_handle)
            self._write_output("VALIDATION RESULTS", file_handle)
            self._write_output("=" * 80, file_handle)
            
            if total_issues == 0:
                self._write_output("STATUS: All enterprise policies are compliant.", file_handle)
                self._write_output("No issues found - configuration meets all organizational requirements.", file_handle)
                self._write_output("=" * 80, file_handle)
                return
            
            if self.errors:
                self._write_output("\n[CRITICAL] POLICY VIOLATIONS - MUST BE FIXED:", file_handle)
                self._write_output("-" * 50, file_handle)
                for i, error in enumerate(self.errors, 1):
                    self._write_output(f"{i:2d}. {error}", file_handle)
                
            if self.warnings:
                self._write_output("\n[WARNING] POLICY RECOMMENDATIONS - SHOULD BE ADDRESSED:", file_handle)
                self._write_output("-" * 60, file_handle)
                for i, warning in enumerate(self.warnings, 1):
                    self._write_output(f"{i:2d}. {warning}", file_handle)
                
            if self.suggestions:
                self._write_output("\n[ADVISORY] OPTIMIZATION SUGGESTIONS - CONSIDER IMPLEMENTING:", file_handle)
                self._write_output("-" * 65, file_handle)
                for i, suggestion in enumerate(self.suggestions, 1):
                    self._write_output(f"{i:2d}. {suggestion}", file_handle)
            
            self._write_output("\n" + "=" * 80, file_handle)
            self._write_output(f"SUMMARY: {len(self.errors)} critical issues, {len(self.warnings)} warnings, {len(self.suggestions)} suggestions", file_handle)
            self._write_output("=" * 80, file_handle)
            
            if output_file and file_handle:
                self._write_output(f"\nValidation report saved to: {output_file}", None)
                
        finally:
            if file_handle:
                file_handle.close()

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Enterprise Databricks Asset Bundle Policy Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This validator enforces enterprise-specific policies that complement the built-in
'dab validate' command. It checks for organizational compliance requirements
including variable usage, naming conventions, required tags, security policies,
and operational best practices.

Exit Codes:
  0 - All validations passed
  1 - Policy violations found (or warnings with --strict mode)
        """
    )
    parser.add_argument("--path", "-p", default=".", help="Path to the DAB project")
    parser.add_argument(
        "--strict", 
        action="store_true", 
        help="Treat warnings as errors (exit code 1)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path for validation report (default: validation/validation_report_TIMESTAMP.txt)"
    )
    args = parser.parse_args()
    
    # Set default output file if not specified
    output_file = args.output
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        validation_dir = Path(args.path) / "validation"
        validation_dir.mkdir(exist_ok=True)
        output_file = validation_dir / f"validation_report_{timestamp}.txt"
    
    validator = EnterpriseDabValidator(args.path)
    is_valid = validator.validate()
    validator.print_results(str(output_file))
    
    # Exit with appropriate code
    if not is_valid or (args.strict and validator.warnings):
        sys.exit(1)

if __name__ == "__main__":
    main()