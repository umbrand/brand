module Test exposing (..)

import Browser
import Html exposing (..)
import Html.Events exposing (onClick)
import Http
import Json.Decode exposing (Decoder, field)
import Process
import Task exposing (Task)

import Browser.Dom

type alias Model =
    { comments : List Comment
    , log : List String
    }


type alias User =
    { id : Int
    , name : String
    }


type alias Post =
    { id : Int
    , userId : Int
    , title : String
    }


type alias Comment =
    { id : Int
    , postId : Int
    , body : String
    }


type Msg
    = GotComments (Result Error (List Comment))
    | GotTest (Result Http.Error String)
    | NoOp


type DataError
    = NoUsers
    | NoPosts


type Error
    = HttpError Http.Error
    | DataError DataError


serverUrl : String
serverUrl =
    "http://localhost:5000/"


userDecoder : Decoder User
userDecoder =
    Json.Decode.map2 User
        (field "id" Json.Decode.int)
        (field "name" Json.Decode.string)


postDecoder : Decoder Post
postDecoder =
    Json.Decode.map3 Post
        (field "id" Json.Decode.int)
        (field "userId" Json.Decode.int)
        (field "title" Json.Decode.string)


commentDecoder : Decoder Comment
commentDecoder =
    Json.Decode.map3 Comment
        (field "id" Json.Decode.int)
        (field "postId" Json.Decode.int)
        (field "body" Json.Decode.string)


handleJsonResponse : Decoder a -> Http.Response String -> Result Http.Error a
handleJsonResponse decoder response =
    case response of
        Http.BadUrl_ url ->
            Err (Http.BadUrl url)

        Http.Timeout_ ->
            Err Http.Timeout

        Http.BadStatus_ { statusCode } _ ->
            Err (Http.BadStatus statusCode)

        Http.NetworkError_ ->
            Err Http.NetworkError

        Http.GoodStatus_ _ body ->
            case Json.Decode.decodeString decoder body of
                Err _ ->
                    Err (Http.BadBody body)

                Ok result ->
                    Ok result


getUsers : Task Http.Error (List User)
getUsers =
    Http.task
        { method = "GET"
        , headers = []
        , url = serverUrl ++ "users"
        , body = Http.emptyBody
        , resolver = Http.stringResolver <| handleJsonResponse <| Json.Decode.list userDecoder
        , timeout = Nothing
        }


getPosts : Int -> Task Http.Error (List Post)
getPosts userId =
    Http.task
        { method = "GET"
        , headers = []
        , url = serverUrl ++ "posts?userId=" ++ String.fromInt userId
        , body = Http.emptyBody
        , resolver = Http.stringResolver <| handleJsonResponse <| Json.Decode.list postDecoder
        , timeout = Nothing
        }


getComments : Int -> Task Http.Error (List Comment)
getComments postId =
    Http.task
        { method = "GET"
        , headers = []
        , url = serverUrl ++ "comments?postId=" ++ String.fromInt postId
        , body = Http.emptyBody
        , resolver = Http.stringResolver <| handleJsonResponse <| Json.Decode.list commentDecoder
        , timeout = Nothing
        }


    
handleTest : Http.Response String -> Result Http.Error String
handleTest response =
    case response of
        Http.BadUrl_ url ->
            Err (Http.BadUrl url)

        Http.Timeout_ ->
            Err Http.Timeout

        Http.BadStatus_ { statusCode } _ ->
            Err (Http.BadStatus statusCode)

        Http.NetworkError_ ->
            Err Http.NetworkError

        Http.GoodStatus_ _ body ->
            Ok body


getUserComments : Task Error (List Comment)
getUserComments =
    getUsers
        |> Task.map List.head
        |> Task.mapError HttpError
        |> Task.andThen
            (\user ->
                case user of
                    Nothing ->
                        Task.fail (DataError NoUsers)

                    Just { id } ->
                        getPosts id
                            |> Task.mapError HttpError
            )
        |> Task.andThen
            (\posts ->
                case Debug.log "posts" posts of
                    [] ->
                        Task.fail (DataError NoPosts)

                    _ ->
                        List.map (getComments << .id) posts
                            |> Task.sequence
                            |> Task.mapError HttpError
            )
        |> Task.map List.concat

getTest : Task Http.Error String
getTest =
    Http.task
        { method = "GET"
        , headers = []
        , url = serverUrl
        , body = Http.emptyBody
        , resolver = Http.stringResolver handleTest
        , timeout = Nothing
        }

init : ( Model, Cmd Msg )
init =
    ( { comments = [], log = [ "Starting requests" ] }
    , Cmd.bath [
    -- (Browser.Dom.focus "BLAH")
    -- |> Task.andThen (\_ -> Task.mapError HttpError |> getTest)
    -- |> Task.mapError HttpError
    -- |> Task.attempt GotTest
    -- |> Task.mapError HttpError
    -- |> Task.andThen (\_ -> getTest) 
    -- |> Task.attempt GotTest
    -- Task.attempt GotTest getTest
    -- |> Task.andThen (\n -> Browser.Dom.focus ("BLAH"))
    )
    -- Task.attempt GotTest getTest)
-- (Browser.Dom.focus ("PostButton"))

errorString : Error -> String
errorString error =
    case error of
        HttpError (Http.BadBody message) ->
            "Unable to handle response: " ++ message

        HttpError (Http.BadStatus statusCode) ->
            "Server error: " ++ String.fromInt statusCode

        HttpError (Http.BadUrl url) ->
            "Invalid URL: " ++ url

        HttpError Http.NetworkError ->
            "Network error"

        HttpError Http.Timeout ->
            "Request timeout"

        DataError NoUsers ->
            "No users"
            
        DataError NoPosts ->
            "No posts"


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        GotComments (Err err) ->
            ( { model | log = errorString err :: model.log }, Cmd.none )

        GotComments (Ok comments) ->
            ( Debug.log "model" { model
                | comments = comments
                , log = ("Got " ++ (String.fromInt <| List.length comments) ++ " comments") :: model.log
              }
            , Cmd.none
            )

        GotTest _  ->
            (  model , Cmd.none )

        NoOp ->
            (model, Cmd.none)



view : Model -> Browser.Document Msg
view model =
    { title = "Example"
    , body = List.intersperse (br [] []) <| List.map text model.log
    }


main : Program () Model Msg
main =
    Browser.document
        { init = \_ -> init
        , view = view
        , update = update
        , subscriptions = \_ -> Sub.none
        }

