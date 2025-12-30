#' Assembling cards on DINA4 sheets
#'
#'@param card_list is a list containing the 57 individual cards
#'@return a list of 10 DINA4 sheets containing 6 dobble cards each
#'@import magick
#'@export

cards_to_A3 <- function(card_list){

  if (length(card_list) < 57){
    stop("Number of dobble cards is smaller than 57. Make sure that 57 cards are supplied")
  }

  if (length(card_list) > 57){
    stop("Number of dobble cards is bigger than 57. Make sure that 57 cards are supplied")
  }

#card_list <- lapply(card_list, image_trim)

vec_of_6 <- list(c(1:6), c(7:12), c(13:18), c(19:24), c(25:30), c(31:36), c(37:42), c(42:48), c(49:54), c(55:57, 55:57))

append_fun <- function(x, y){
  sheet <- image_append(c(image_append(c(y[[x[1]]],y[[x[2]]])),
                          image_append(c(y[[x[3]]],y[[x[4]]])),
                          image_append(c(y[[x[5]]],y[[x[6]]]))), stack=TRUE )
  #sheet<- image_scale(sheet, "4960") #A3 half for A4
  return(sheet)
  }

sheet_list <- lapply(vec_of_6, append_fun, card_list)

return(sheet_list)

}


