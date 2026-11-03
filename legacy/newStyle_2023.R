library(ggplot2)
#library(ggforce)
#library(writexl)
library(readxl)
library(dplyr)
library(magick)

source("R3/Functions.R")
source("R3/dobble_template.R")
source("r3/cards_to_DINA4.R")

circles<-read_excel("circles.xlsx")
selected_size<-550

CardSizeInPixels<-selected_size*2
bigCircleRadius<-selected_size


#create cricut template.
#cricut has 144 resolution.

cx<-(209.97/747.45)*100

cy<-(296.93/1135.49)*100

#cy<-cx<-100
img<-createCircleCricut(CardSizeInPixels,bigCircleRadius)


vector_images<- c(img,img)
img<-image_append(vector_images)

vector_images<- c(img,img,img)
img<-image_append(vector_images,stack = TRUE)
img<-image_resize(img, geometry_size_percent(cx, cy))
image_write(img, path = "cricut.png", format = "png")
img<-image_read("cricut.png")
img


file_name<-"easy.csv"
file_name<-paste0("dataFiles/",file_name)
allWords<- read.csv(file_name)

colour_options <- c("blue","gold2","darkmagenta","firebrick3","darkolivegreen4", "purple","aquamarine","chartreuse4","brown2","darkorchid1","darkslategrey","darkorange2")

wordsAndColours<-data.frame(words = allWords[,2],
                            wordColour= sample(colour_options,57,replace = TRUE)
                            )

deck<-dobble_template()

for (thisCardNo in 1:57)
{

  thisCircleSet<-circle_parameter(selected_size,circles)

thisCard<- data.frame(
                      wordsAndColours[unlist(deck[thisCardNo]),],
                      angle =sample(1:360, 8),
                      x = thisCircleSet$x,
                      y = thisCircleSet$y,
                      radius = thisCircleSet$Radius
                      )

img<- makeOneCard(thisCard,
                  CardSizeInPixels,
                  bigCircleRadius
                  )

file_name<-paste0("output/words/Card_",thisCardNo,".png")
image_write(img, path = file_name, format = "png")
}

outfolder<-'output/cards'



all_cards <- lapply(list.files(path='output/words/'), function(x) image_read(paste0('output/words',"/",x)))

sheet_list <- cards_to_A3(all_cards)

lapply(seq_along(sheet_list), function(y, i){image_write(y[[i]],
                                                         path=paste0(outfolder, "/sheet",i, ".png"),
                                                         format="png",
                                                         density = 300)
                                            }, y=sheet_list)

