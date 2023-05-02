###########################################################
# GCP_Bucket/main.tf
###########################################################
# Variables
###########################################################
variable "message" {
  default = "Hello world"
}
###########################################################
# Provider
###########################################################
provider "kubernetes" {
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
resource "kubernetes_config_map" "example" {
  metadata {
    name = "html-${random_id.id.hex}"
  }

  data = {
    "index.html" = "<html><head><title>${var.message}</title></head><body><h1>${var.message}</h1></body></html>"
  }
}

output "bucket" {
  value = "${random_id.id.hex}"
}