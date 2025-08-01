#!/bin/bash

# Local DAB Validation Script
# Run this script before pushing to ensure your changes will pass CI/CD validation

set -e

echo "==============================================================================="
echo "🔍 LOCAL DAB VALIDATION SCRIPT"
echo "==============================================================================="
echo "This script runs the same validations as the GitHub Actions workflow."
echo "Run this before pushing to catch issues early!"
echo "==============================================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    case $1 in
        "ERROR")   echo -e "${RED}❌ $2${NC}" ;;
        "SUCCESS") echo -e "${GREEN}✅ $2${NC}" ;;
        "WARNING") echo -e "${YELLOW}⚠️  $2${NC}" ;;
        "INFO")    echo -e "${BLUE}ℹ️  $2${NC}" ;;
    esac
}

# Check if we're in a DAB project directory
if [ ! -f "databricks.yml" ]; then
    print_status "ERROR" "databricks.yml not found. Please run this script from the root of your DAB project."
    exit 1
fi

# Check if validation script exists
if [ ! -f "validation/enterprise_dab_validator.py" ]; then
    print_status "ERROR" "Enterprise validation script not found at validation/enterprise_dab_validator.py"
    exit 1
fi

# Determine target environment (default to dev)
TARGET_ENV="${1:-dev}"
print_status "INFO" "Using target environment: $TARGET_ENV"

echo ""
echo "==============================================================================="
echo "STEP 1: DATABRICKS BUNDLE VALIDATION"
echo "==============================================================================="

if databricks bundle validate --target "$TARGET_ENV"; then
    print_status "SUCCESS" "Databricks bundle validation passed"
    DAB_VALIDATION_RESULT="PASSED"
else
    print_status "ERROR" "Databricks bundle validation failed"
    DAB_VALIDATION_RESULT="FAILED"
fi

echo ""
echo "==============================================================================="
echo "STEP 2: ENTERPRISE POLICY VALIDATION"
echo "==============================================================================="

if python validation/enterprise_dab_validator.py --path . --strict; then
    print_status "SUCCESS" "Enterprise policy validation passed"
    ENTERPRISE_VALIDATION_RESULT="PASSED"
else
    print_status "ERROR" "Enterprise policy validation failed"
    ENTERPRISE_VALIDATION_RESULT="FAILED"
fi

echo ""
echo "==============================================================================="
echo "VALIDATION SUMMARY"
echo "==============================================================================="

echo "Target Environment: $TARGET_ENV"
echo "Databricks Bundle Validation: $DAB_VALIDATION_RESULT"
echo "Enterprise Policy Validation: $ENTERPRISE_VALIDATION_RESULT"

if [ "$DAB_VALIDATION_RESULT" = "PASSED" ] && [ "$ENTERPRISE_VALIDATION_RESULT" = "PASSED" ]; then
    echo ""
    print_status "SUCCESS" "All validations passed! Your changes are ready for deployment."
    echo ""
    echo "📋 Next steps:"
    echo "   • Review the validation report in validation/ directory"
    echo "   • Commit and push your changes"
    echo "   • The GitHub Actions workflow will automatically deploy to $TARGET_ENV"
    echo ""
    exit 0
else
    echo ""
    print_status "ERROR" "Validation failures detected. Please fix the issues before pushing."
    echo ""
    echo "🔧 How to fix:"
    echo "   • Check the validation report in validation/ directory"
    echo "   • Review the error messages above"
    echo "   • Run this script again after making fixes"
    echo ""
    exit 1
fi