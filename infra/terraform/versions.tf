# Configures Terraform itself, not a cloud resource.
terraform {
  # Refuse older Terraform than this: a colleague on 1.4 would get a parse
  # error that does not mention versions.
  required_version = ">= 1.9"

  required_providers {
    google = {
      source = "hashicorp/google"
      # ~> 8.4 = 8.4 and later 8.x, never 9.x by surprise (same argument as the
      # image pinning of L06). The resolved version is in .terraform.lock.hcl,
      # which is committed.
      version = "~> 8.4"
    }
  }

  # State lives in a versioned bucket, not on a laptop. The bucket was created
  # by hand (Terraform cannot create the place it keeps its own state): see
  # docs/infra.md and docs/adr/0008-remote-state.md. The backend block cannot
  # use variables, so the name is written out.
  backend "gcs" {
    bucket = "data-engineering-a-groupe-julius-tfstate"
    prefix = "platform"
  }
}
