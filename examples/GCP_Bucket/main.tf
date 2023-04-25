###########################################################
# GCP_Bucket/main.tf
###########################################################
# Variables
###########################################################
variable "domain_name" {
  default = "kappform-dev"
}
###########################################################
# Provider
###########################################################
provider "google" {
  region      = "eu-west-9"
}
###########################################################
# Random
###########################################################
resource "random_id" "id" {
  byte_length = 8
}
###########################################################
# Resources
###########################################################
resource "google_storage_bucket" "static-site" {
  name          = "${var.domain_name}-${random_id.id.hex}"
  location      = "EU"
  force_destroy = true
}

output "bucket" {
  value = google_storage_bucket.static-site.name
}