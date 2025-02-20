provider "aws" {
  region = var.region
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0.0"
    }
  }
  #   backend "s3" {
  #     bucket         = "my-terraform-state-bucket"
  #     key            = "infrastructure/terraform.tfstate"
  #     region         = "ap-south-1"
  #     encrypt        = true
  #     dynamodb_table = "terraform-state-lock"
  #   }
}