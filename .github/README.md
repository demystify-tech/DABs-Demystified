# GitHub Actions Setup for DAB Validation and Deployment

This directory contains GitHub Actions workflows for automated validation and deployment of Databricks Asset Bundles (DABs) with enterprise policy compliance.

## 🔧 Setup Instructions

### 1. Required Secrets

Configure the following secrets in your GitHub repository settings (`Settings > Secrets and variables > Actions`):

#### Development Environment
- `DATABRICKS_HOST`: Your Databricks workspace URL (e.g., `https://your-workspace.cloud.databricks.com`)
- `DATABRICKS_TOKEN`: Personal access token for development environment

#### Production Environment
- `DATABRICKS_HOST_PROD`: Databricks workspace URL for production
- `DATABRICKS_TOKEN_PROD`: Personal access token for production environment

### 2. Databricks Personal Access Token Setup

1. Go to your Databricks workspace
2. Click on your user profile → User Settings
3. Go to Access tokens tab
4. Generate new token with appropriate permissions
5. Copy the token and add it to GitHub secrets

### 3. Environment Protection (Recommended)

For production deployments, set up environment protection:

1. Go to `Settings > Environments` in your repository
2. Create an environment named `production`
3. Add protection rules:
   - Required reviewers (recommended: 2+ reviewers)
   - Wait timer (optional: 5-10 minutes)
   - Restrict to specific branches (main/master)

## 📋 Workflows

### 1. DAB Validation and Deployment (`dab-validation-deployment.yml`)

**Triggers:** 
- Push to `dev` branch
- Pull requests targeting `dev` branch

**Steps:**
1. ✅ Checkout code
2. 🐍 Setup Python environment
3. 📦 Install dependencies (Databricks CLI, validation requirements)
4. 🔗 Configure Databricks authentication
5. ✔️ Run `databricks bundle validate`
6. 🏢 Run enterprise policy validation (strict mode)
7. 📄 Upload validation report as artifact
8. 🚀 Deploy to development environment (only if all validations pass)
9. 💬 Comment on PR with validation results

### 2. Production Deployment (`production-deployment.yml`)

**Triggers:**
- Push to `main` branch
- Manual workflow dispatch

**Features:**
- Environment protection (requires approval)
- Strict validation mode
- Extended artifact retention (90 days)
- Manual environment selection
- Enhanced notification system

## 🔍 Validation Process

### Stage 1: Databricks Bundle Validation
- Validates DAB configuration syntax
- Checks resource definitions
- Verifies workspace connectivity

### Stage 2: Enterprise Policy Validation
- ✅ **Variable usage policy**: Sensitive fields must use variables
- 🏷️ **Required tags**: `cost_center`, `environment`, `team`
- 📝 **Naming conventions**: Proper job and cluster naming
- 🔐 **Security compliance**: No hardcoded secrets, secure paths
- 💰 **Cost optimization**: Worker limits, node type suggestions
- ✨ **Best practices**: Email notifications, timeouts, retry logic

### Stage 3: Deployment
- Only runs if both validations pass
- Deploys to appropriate environment based on branch
- Provides deployment summary and status

## 📊 Artifacts and Reports

### Validation Reports
- Generated for every workflow run
- Uploaded as GitHub Actions artifacts
- Contains detailed policy compliance analysis
- Available in workflow run details

### Report Contents
- Timestamp and project information
- Critical policy violations
- Warnings and recommendations
- Optimization suggestions
- Summary statistics

## 🚨 Failure Scenarios

### Validation Failures
- ❌ Deployment is **blocked**
- 📋 Detailed error report uploaded as artifact
- 💬 PR comment with failure summary (for PRs)
- 🔍 Check workflow logs for specific issues

### Common Issues
1. **Missing required tags**: Add `team`, `cost_center`, `environment` tags
2. **Hardcoded values**: Use variables for sensitive fields
3. **Naming violations**: Follow capital letter convention for jobs
4. **Security issues**: Remove hardcoded secrets, fix paths

## 🎯 Best Practices

### For Developers
1. Run validations locally before pushing:
   ```bash
   databricks bundle validate --target dev
   python validation/enterprise_dab_validator.py --strict
   ```

2. Always test in development environment first
3. Follow enterprise naming conventions
4. Use variables for environment-specific values
5. Include required tags in all resources

### For Administrators
1. Regularly review validation reports
2. Update enterprise policies as needed
3. Monitor deployment success rates
4. Set up appropriate branch protection rules
5. Configure environment-specific secrets properly

## 🔧 Customization

### Modifying Validation Rules
- Edit `validation/enterprise_dab_validator.py`
- Update required tags, naming patterns, or policies
- Test changes in development environment first

### Environment Configuration
- Modify target environments in workflow files
- Update secret names for different environments
- Adjust artifact retention periods as needed

### Notification Integration
- Add Slack/Teams webhooks for deployment notifications
- Integrate with ticketing systems for failure tracking
- Set up email alerts for production deployments

## 📚 Additional Resources

- [Databricks Asset Bundles Documentation](https://docs.databricks.com/dev-tools/bundles/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Databricks CLI Setup](https://docs.databricks.com/dev-tools/cli/)