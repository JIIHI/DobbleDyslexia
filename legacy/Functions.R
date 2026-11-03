WhatSizeFont<-function(thisSize,angle,thisWord)
{
  font_size<-10
  text_height<-text_width<-0
  maxSize<-thisSize

  while((text_height <  maxSize) & (text_width < maxSize)){
    font_size<-as.integer(font_size*1.1)
    img <- image_blank(2000,2000, color = "none")
    img <- image_annotate(
      img,
      thisWord,
      gravity = "center",
      location = "+0+0",
      degrees = angle,
      size = font_size,
      font = "",
      style = "normal",
      weight = 400,
      kerning = 0,
      decoration = NULL,
      color = "red",
      strokecolor = NULL,
      boxcolor = NULL
    )
    img <- image_trim(img)
    info <- image_info(img)
    text_width <- info$width
    text_height <- info$height
  }
  img<-NULL
  return (font_size-1)
}

createCirclePNG<-function(CardSizeInPixels,big_circle_radius)
{
  # Create a PNG file to save the circle
  png("circleBorder.png", width = CardSizeInPixels, height = CardSizeInPixels)
  plot.new()
  par(mar = c(0, 0, 0, 0))
  plot.window(xlim = c(0, CardSizeInPixels), ylim = c(0, CardSizeInPixels))
  # Draw the circle
  symbols(x = big_circle_radius, y = big_circle_radius, circles = big_circle_radius,
          inches = FALSE, add = TRUE, fg = "black", bg = "white")
  # Turn off the device (this finalizes and saves the PNG file)
  dev.off()


  # Start drawing on the canvas
  img <- image_blank(CardSizeInPixels,CardSizeInPixels, color = "none")
  circleBorder<-circle_image <- image_read("circleBorder.png")
  #circleBorder<-image_trim(circleBorder)
  img <- image_composite(img, circleBorder, offset = "+0+0", operator = "over")
  return(img)
}


createCircleCricut<-function(CardSizeInPixels,big_circle_radius)
{
  # Create a PNG file to save the circle
  png("circleBorder.png", width = CardSizeInPixels, height = CardSizeInPixels)
  plot.new()
  par(mar = c(0, 0, 0, 0))
  plot.window(xlim = c(0, CardSizeInPixels), ylim = c(0, CardSizeInPixels))
  # Draw the circle
  symbols(x = big_circle_radius, y = big_circle_radius, circles = big_circle_radius,
          inches = FALSE, add = TRUE, fg = "black", bg = "black")
  # Turn off the device (this finalizes and saves the PNG file)
  dev.off()


  # Start drawing on the canvas
  img <- image_blank(CardSizeInPixels,CardSizeInPixels, color = "none")
  circleBorder<-circle_image <- image_read("circleBorder.png")
  img <- image_composite(img, circleBorder, offset = "+0+0", operator = "over")
  return(img)
}


BuildCard<-function(img,angle,thisWord,thisFontSize,thisWordColor,x,y)
{
  img <- image_annotate(
    img,
    thisWord,
    gravity = "center",
    location = paste0("+",x,"+",y),
    degrees = angle,
    size = thisFontSize,
    font = "",
    style = "normal",
    weight = 400,
    kerning = 0,
    decoration = NULL,
    color = thisWordColor,
    strokecolor = NULL,
    boxcolor = NULL
  )
  return(img)
}

makeOneCard<-function(thisCard,CardSizeInPixels,bigCircleRadius)
{

  img<-createCirclePNG(CardSizeInPixels,bigCircleRadius)

  for (ct in 1:8) {
    thisFontSize<-WhatSizeFont(thisSize = thisCard$radius[ct],
                               angle = thisCard$angle[ct],
                               thisWord = thisCard$words[ct]
    )

    img<-BuildCard(img=img,
                   angle = thisCard$angle[ct],
                   thisWord = thisCard$words[ct],
                   thisFontSize = thisFontSize,
                   thisWordColor = thisCard$wordColour[ct],
                   x = thisCard$x[ct],
                   y = thisCard$y[ct])

  }
  return(img)
}

circle_parameter<-function(selected_size,circles)
{
  filter<-circles$big_circle_radius == selected_size
  circles<-circles[filter,]

  circle_ids<-unique(circles$bigCircle_id)

  random_circle<-sample(circle_ids,1)

  thisCircleSet<- circles %>%
    filter(bigCircle_id == random_circle)

  return(thisCircleSet)

}
