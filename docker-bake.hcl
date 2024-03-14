variable "TAG" {
    default = "1.0.0"
}

variable "REGISTRY" {
    default = "duplocloud/duploctl"
}

group "default" {
    targets = ["duploctl"]
}

target "duploctl" {
    tags = [
        "${REGISTRY}:latest",
        "${REGISTRY}:${TAG}"
    ]
    platforms = [
        "linux/amd64",
        "linux/arm64"
    ]
    
}
