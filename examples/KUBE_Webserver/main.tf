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
resource "kubernetes_service" "example" {
  metadata {
    name = "svc-webserver-${random_id.id.hex}"
  }
  spec {
    selector = {
      app = kubernetes_pod.example.metadata.0.labels.app
    }
    session_affinity = "ClientIP"
    port {
      port        = 8080
      target_port = 80
    }

    type = "NodePort"
  }
}

resource "kubernetes_pod" "example" {
  metadata {
    name = "webserver-${random_id.id.hex}"
    labels = {
      app = "webserver-${random_id.id.hex}"
    }
  }

  spec {
    container {
      image = "nginx:1.21.6"
      name  = "webserver"
    
      volume_mount {
        mount_path = "/usr/share/nginx/html"
        name = "html"
      }
    }
    volume {
      name = "html"
      config_map {
        name = "html-${random_id.id.hex}"
      }
    }
  }
}

output "bucket" {
  value = "${random_id.id.hex}"
}