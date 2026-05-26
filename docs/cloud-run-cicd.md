# Cloud Run GitHub Auto-Deploy

This repo deploys to Google Cloud Run automatically when commits land on `main`.

## One-time Google Cloud setup

Run these commands from any terminal where `gcloud` is logged into the `gpr-thickness-map` project.

```powershell
$ProjectId = "gpr-thickness-map"
$Repo = "bShakya221/GPR-thickness-heatmap"
$PoolId = "github-actions"
$ProviderId = "github"
$DeployServiceAccountName = "github-cloud-run-deployer"
$DeployServiceAccount = "$DeployServiceAccountName@$ProjectId.iam.gserviceaccount.com"
$ProjectNumber = gcloud projects describe $ProjectId --format="value(projectNumber)"

gcloud config set project $ProjectId

gcloud services enable `
  run.googleapis.com `
  cloudbuild.googleapis.com `
  artifactregistry.googleapis.com `
  iamcredentials.googleapis.com `
  sts.googleapis.com `
  serviceusage.googleapis.com

gcloud iam service-accounts create $DeployServiceAccountName `
  --display-name "GitHub Cloud Run deployer"

gcloud projects add-iam-policy-binding $ProjectId `
  --member "serviceAccount:$DeployServiceAccount" `
  --role "roles/run.sourceDeveloper"

gcloud projects add-iam-policy-binding $ProjectId `
  --member "serviceAccount:$DeployServiceAccount" `
  --role "roles/serviceusage.serviceUsageConsumer"

gcloud iam service-accounts add-iam-policy-binding "$ProjectNumber-compute@developer.gserviceaccount.com" `
  --project $ProjectId `
  --member "serviceAccount:$DeployServiceAccount" `
  --role "roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $ProjectId `
  --member "serviceAccount:$ProjectNumber-compute@developer.gserviceaccount.com" `
  --role "roles/run.builder"

gcloud iam workload-identity-pools create $PoolId `
  --project $ProjectId `
  --location "global" `
  --display-name "GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc $ProviderId `
  --project $ProjectId `
  --location "global" `
  --workload-identity-pool $PoolId `
  --display-name "GitHub" `
  --issuer-uri "https://token.actions.githubusercontent.com" `
  --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" `
  --attribute-condition "assertion.repository == '$Repo' && assertion.ref == 'refs/heads/main'"

gcloud iam service-accounts add-iam-policy-binding $DeployServiceAccount `
  --project $ProjectId `
  --role "roles/iam.workloadIdentityUser" `
  --member "principalSet://iam.googleapis.com/projects/$ProjectNumber/locations/global/workloadIdentityPools/$PoolId/attribute.repository/$Repo"
```

## Add GitHub secrets

In GitHub, add these repository secrets:

```text
GCP_WORKLOAD_IDENTITY_PROVIDER=projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions/providers/github
GCP_SERVICE_ACCOUNT=github-cloud-run-deployer@gpr-thickness-map.iam.gserviceaccount.com
```

Replace `PROJECT_NUMBER` with the value printed by:

```powershell
gcloud projects describe gpr-thickness-map --format="value(projectNumber)"
```

If you use GitHub CLI:

```powershell
$ProjectNumber = gcloud projects describe gpr-thickness-map --format="value(projectNumber)"
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --body "projects/$ProjectNumber/locations/global/workloadIdentityPools/github-actions/providers/github"
gh secret set GCP_SERVICE_ACCOUNT --body "github-cloud-run-deployer@gpr-thickness-map.iam.gserviceaccount.com"
```

## Verify

Push to `main`, then open the GitHub Actions tab for this repository and watch the `Deploy to Cloud Run` workflow. The last step calls `/api/health`; a failed health response fails the deployment workflow.
