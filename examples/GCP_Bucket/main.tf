###########################################################
# GCP_Bucket/main.tf
###########################################################
# Variables
###########################################################
variable "domain_name" {
  default = "example.com"
}
###########################################################
# Provider
###########################################################
provider "google" {
  region      = "eu-west-9"
}

###########################################################
# Resources
###########################################################
resource "google_storage_bucket" "static-site" {
  name          = "${var.domain_name}"
  location      = "EU"
  force_destroy = true

  uniform_bucket_level_access = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "404.html"
  }
  cors {
    origin          = ["${var.domain_name}"]
    method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}