```r
# ============================================================================
# ORGANIC CIRCLE GROWTH SIMULATION
# ============================================================================
# Simulates the organic growth and spatial arrangement of circles within
# a boundary circle. Implements physics-based collision detection and
# growth inhibition to create realistic, balanced packing patterns.
# ============================================================================

library(writexl)    # write_xlsx() - Export circle data to Excel format
library(readxl)     # read_excel() - Read existing circle data from Excel files

# --- Constants ---
big_circle_radius <- 550      # Boundary circle radius
n_small_circles <- 8          # Number of circles to simulate
growth_factor <- 1            # Base growth factor (overridden in loop)
max_coverage <- 0.68          # Max fill % before growth stops
max_ratio <- 1.6              # Max size ratio (largest/smallest)

# --- Helper Functions ---

# Generate random seed points uniformly distributed within a circle
generate_random_points <- function(n, big_radius) {
  points <- matrix(0, ncol = 2, nrow = n)
  for (i in 1:n) {
    angle <- runif(1, 0, 2*pi)
    radius <- sqrt(runif(1, 0, big_radius^2))
    points[i,] <- c(radius*cos(angle), radius*sin(angle))
  }
  return(points)
}

# Check if two circles overlap
do_circles_overlap <- function(x1, y1, r1, x2, y2, r2) {
  return(sqrt((x1-x2)^2 + (y1-y2)^2) < (r1 + r2))
}

compute_force <- function(x, y, radii, idx, big_circle_radius) {
  force_x <- 0
  force_y <- 0

  # Forces from overlapping circles
  for (i in 1:length(radii)) {
    if (i != idx) {
      if (do_circles_overlap(x[idx], y[idx], radii[idx], x[i], y[i], radii[i])) {
        # Compute repulsion vector from circle i to circle idx
        dx <- x[idx] - x[i]
        dy <- y[idx] - y[i]
        mag <- sqrt(dx^2 + dy^2)
        dx <- dx / mag
        dy <- dy / mag

        # Calculate overlap magnitude
        overlap <- radii[idx] + radii[i] - mag

        force_x <- force_x + overlap * dx
        force_y <- force_y + overlap * dy
      }
    }
  }

  # Force from boundary circle constraint
  distance_to_center <- sqrt(x[idx]^2 + y[idx]^2)

  if ((distance_to_center + radii[idx]) > big_circle_radius) {
    overlap_with_big_circle <- (distance_to_center + radii[idx]) - big_circle_radius

    # Unit direction vector pointing toward center
    dx_center <- -x[idx] / distance_to_center
    dy_center <- -y[idx] / distance_to_center

    force_x <- force_x + overlap_with_big_circle * dx_center
    force_y <- force_y + overlap_with_big_circle * dy_center
  }

  return(c(force_x, force_y))
}

plot_circles <- function(x, y, radii, big_circle_radius) {
  # Create plot with equal aspect ratio
  plot(NA, xlim = c(-big_circle_radius, big_circle_radius),
       ylim = c(-big_circle_radius, big_circle_radius),
       xlab = "", ylab = "", asp = 1)

  # Draw the boundary circle
  symbols(0, 0, circles = big_circle_radius, add = TRUE, inches = FALSE)

  # Draw all small circles
  symbols(x, y, circles = radii, add = TRUE, inches = FALSE)
}

# Normalize vector to [0, 1] range
normalize <- function(x) {
  return ((x - min(x)) / (max(x) - min(x)))
}

# Normalize vector to [0, max(x)] range
normalize1 <- function(x) {
  return (x / max(x))
}

# Sigmoid function for growth capping
# Prevents largest circles from dominating
sigmoid <- function(x_all, x, c = max_ratio, k = 0.5) {
  r <- x / min(x_all)
  sigmoid_value <- 1 / (1 + exp(-k * (r - c)))
  return(sigmoid_value)
}

# Save circle configuration to Excel file
# Appends to existing file or creates new one
write_circles <- function(big_ID = 1,
                          n_small_circlesf = n_small_circles,
                          xf = x,
                          yf = y,
                          radiif = radii,
                          big_circle_radiusf = big_circle_radius) {
  df_circles <- data.frame(
    bigCircle_id = big_ID,
    CircleID = 1:n_small_circlesf,
    x = xf,
    y = yf,
    Radius = radiif,
    big_circle_radius = big_circle_radiusf
  )

  if (file.exists("circles.xlsx")) {
    circles_xls <- read_excel("circles.xlsx")
    big_ID <- circles_xls[nrow(circles_xls), 1] + 1
    df_circles <- data.frame(
      bigCircle_id = big_ID,
      CircleID = 1:n_small_circlesf,
      x = xf,
      y = yf,
      Radius = radiif,
      big_circle_radius = big_circle_radiusf
    )
    df_circles <- rbind(circles_xls, df_circles)
  }

  write_xlsx(df_circles, "circles.xlsx")
}


# --- Main Simulation Loop ---
seeds <- generate_random_points(n_small_circles, big_circle_radius)
x <- seeds[,1]
y <- seeds[,2]
radii <- rep(3, n_small_circles)  # Initialize all circles with radius 3

for (step in steps <- 1:300) {
  # --- Growth Phase ---
  inhibition <- 0
  g_value <- numeric()
  inhibition_all <- numeric()

  # Calculate inhibitory effect from all other circles on each circle
  for (i in 1:n_small_circles) {
    for (j in 1:n_small_circles) {
      if (i != j) {
        distance <- sqrt((x[i] - x[j])^2 + (y[i] - y[j])^2)
        # Inhibition: larger and closer circles exert stronger inhibition
        inhibition <- inhibition + (radii[j] / (distance + 1))
      }
    }
    inhibition_all[i] <- inhibition
  }

  normalized_inhibition <- normalize1(inhibition_all)

  # Calculate maturation (current coverage as % of boundary circle)
  current_combined_area <- sum(pi * radii^2)
  maturation <- current_combined_area / (big_circle_radius^2 * pi)
  sign_g <- (max_coverage - maturation)
  print(maturation)

  # Calculate growth cap: prevents size ratio from exceeding max_ratio
  growthcap <- numeric()
  growth_factor <- 10

  for (i in 1:n_small_circles) {
    growthcap[i] <- sigmoid(radii, radii[i], growth_factor, .05)
  }

  print(growthcap)

  # Calculate growth increment for each circle
  q <- 1 / growthcap
  q <- q - normalized_inhibition
  q <- q * sign_g

  radii <- radii + q

  # --- Movement Phase ---
  # Update positions based on collision forces
  for (i in 1:n_small_circles) {
    force <- compute_force(x, y, radii, i, big_circle_radius)
    x[i] <- x[i] + force[1]
    y[i] <- y[i] + force[2]
  }

  # Plot every 10 steps for visualization
  if (step %% 10 == 0) {
    plot_circles(x, y, radii, big_circle_radius)
  }
}

sx <- as.integer(x)
sy <- as.integer(y)
sradii <- as.integer(radii)

plot_circles(x, y, radii, big_circle_radius)

write_circles()
```
