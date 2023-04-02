###########################################################
# AWS_BucketS3/main.tf
###########################################################
# Variables
###########################################################
variable "region" {
  default = "us-west-2"
}
variable "domain_name" {
  default = "example.com"
}
###########################################################
# Provider
###########################################################
provider "aws" {
  region = "${var.region}"
}

###########################################################
# Resources
###########################################################
resource "aws_s3_bucket" "site" {
  bucket = "${var.domain_name}"
  region = "${var.region}"
  acl = "public-read"
  website {
    index_document = "index.html"
    error_document = "error.html"
  }
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadForGetBucketObjects",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": ["arn:aws:s3:::${var.domain_name}/*"]
  }]
}
EOF
}