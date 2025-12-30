#' dobble_template
#'
#' Creates a list of dobble cards using numbers instead of images
#' @return vector
#' @export
#' @examples
#' dobble_template()

dobble_template <- function(){

  n <- 8 ##probably n needs to be 8
  listlength <- (n-1)*(n-1)+n
  cardlist <- vector(mode = "list", length = listlength)

  ## first card
  card1 <- integer(n)
  for (i in 1:n) {
    card1[i] <- i
  }
  cardlist[[1]] <- card1

  ## following cards
  for (j in 1:(n-1)) {
    card <- integer(n)
    for (k in 0:(n-1)) {
      part <- (n +(n-1)*(j-1) + k)
      card[1]<- 1
      card[k+1]<- part
    }
    cardlist[[j+1]]<- card
  }
  ##following cards afterwards

  for (i in 0:(n-2)){
    for (j in 0:(n-2)) {
      card <- integer(n)
      for (k in 0:(n-2)) {
        part <- (n + 1+ (n-1)*k + (i*k+j)%%(n-1)); # Good for n = prime number
        card[1] <- i+2
        card[k+2]<- part
      }
      cardnumber <- n+1+j+((n-1)*i)
      cardlist[[cardnumber]] <- card
    }
  }
  return(cardlist)
}
