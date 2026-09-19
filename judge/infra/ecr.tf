resource "aws_ecr_repository" "judge" {
  name                 = var.app_name
  image_tag_mutability = "MUTABLE" # App Runner auto-deploy watches this tag for new pushes

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "judge" {
  repository = aws_ecr_repository.judge.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the 10 most recent images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}
