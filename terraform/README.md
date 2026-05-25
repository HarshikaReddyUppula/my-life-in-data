# Terraform

Provisions the AWS side of the lakehouse: two S3 buckets (Bronze + Silver) and a Glue IAM role.

## Usage

```bash
terraform init
terraform plan
terraform apply
```

Outputs the bucket names + role ARN you'll need for `.env` and the Glue job submission.

## State

State is stored locally by default. For a real deployment, configure an S3 backend:

```hcl
terraform {
  backend "s3" {
    bucket = "harshika-tf-state"
    key    = "my-life-in-data/terraform.tfstate"
    region = "us-east-1"
  }
}
```

## Cost

Free tier covers all of this for personal-scale data. S3 standard is ~$0.023/GB-month.
