{-

View the live streaming of parameters in the system

David Brandman


This code begins by asking the rest server for information of what streams are available:

/streams

This will return a JSON which indicates the streams, and for each stream a list of keys and parameters accepted by the server. It then generates HTML selects pre-populated with this JSON list, giving the user the opportunity to select a specific stream. Next, the code asks for:

/streams/[stream]/[stream key]?parameters

And then gets a JSON back with the data

Data that are exported:

- Stream : The type that contains the encapsulated information used by Main's model
- Msg    : Since Main has to pass messages around, it has to know about Stream's Msg


TODO: 
1. the way empty streams are handled is quite lazy. It would be better if it were a Maybe rather than just relying on checking if the records match an empty

-}

port module Stream exposing (Stream, Msg, displayStream, updateStream, initializeStream, initializeStreamCommand, tick, getRefreshRate, runCommand )

import Browser
import Browser.Dom
import Html exposing (..)
import Html.Attributes exposing ( attribute, style, src, placeholder, type_, href, rel, class, value , classList , id)
import Html.Events exposing (onClick, onInput, onCheck)

import Http

import Json.Decode
import Json.Decode.Pipeline
import Json.Encode

import Task
import Time
import Dict exposing (Dict)

import List.Extra


--------------------------------------------------
--------------------------------------------------
-- Exports
--------------------------------------------------
--------------------------------------------------

-- The encapsulated Model around type Stream.

initializeStream : Stream
initializeStream =
    emptyModel
    |> Stream

-- You give me the Stream, and I render it

displayStream : Stream -> Html Msg
displayStream stream = 
    case stream of
        Stream model -> view model

-- You give me a Stream.Msg, and then I update the model

updateStream : Msg -> Stream -> Stream
updateStream msg stream =
    case stream of
        Stream model ->
            update msg model
            |> Tuple.first
            |> Stream

-- Code for dealing with HTTP Get /streams

initializeStreamCommand : String -> Cmd Msg
initializeStreamCommand url =
    getStreamList url

-- Managing the results of a subscription update



-- Return the model refresh rate

getRefreshRate: Stream -> Maybe Float
getRefreshRate stream =
    case stream of
        Stream model -> model.refreshRate

runCommand : String -> Msg -> Cmd Msg
runCommand url msg =
    Cmd.none

--------------------------------------------------
--------------------------------------------------
-- MAIN and PORTS
--------------------------------------------------
--------------------------------------------------

-- main =
--   Browser.element
--     { init          = init
--     , update        = update
--     , subscriptions = subscriptions
--     , view          = view
--     }

-- subscriptions : Model -> Sub Msg
-- subscriptions model =
--     Sub.none

port toJS_plotly2 : List Json.Encode.Value -> Cmd msg

portJson : Model -> Cmd msg
portJson model =
    [ model |> plotlyJsonData
    , model |> plotlyJsonLayout
    ]
    |> toJS_plotly2


--------------------------------------------------
--------------------------------------------------
-- MODEL and INIT
--------------------------------------------------
--------------------------------------------------


type Stream = Stream Model

type alias StreamInfo =
    { name       : String
    , keys       : List String
    , parameters : List String
    }

type alias StreamList =
    { streams : List StreamInfo }

type alias StreamData =
    { name   : String
    , x      : List Float
    , y      : List Float
    , xTitle : String
    , yTitle : String
    , maxID  : String
    }

-- TODO: Turn these into maybes
type alias SelectedStream =
    { name       : String
    , key        : String
    , parameters : Dict String String
    }

emptyStreamInfo : StreamInfo
emptyStreamInfo = 
    { name       = ""
    , keys       = []
    , parameters = []
    }

emptyStreamList : StreamList
emptyStreamList =
    { streams = [] }

emptyStreamData : StreamData
emptyStreamData =
    { name   = "Empty"
    , x      = [1,2,3,4,5]
    , y      = [1,2,3,4,5]
    , xTitle = "Empty X"
    , yTitle = "Empty X"
    , maxID  = "0-0"
    }

type SelectedStreamType =
      SelectedStreamName String
    | SelectedStreamKey String
    | SelectedStreamParameter String String

emptySelectedStream : SelectedStream
emptySelectedStream =
    { name = ""
    , key  = ""
    , parameters = Dict.empty 
    }

type alias Model =
    { refreshRate    : Maybe Float
    , selectedStream : SelectedStream
    , streamList     : List StreamInfo
    , streamData     : StreamData
    , url            : String
    }

emptyModel : Model
emptyModel =
    { refreshRate    = Just 1000.0
    , selectedStream = emptySelectedStream
    , streamList     = []
    , streamData     = emptyStreamData
    , url            = ""
    }


-- init : () -> (Model, Cmd Msg)
-- init _ =
--     (emptyModel, getStreamList )


--------------------------------------------------
--------------------------------------------------
-- UPDATE
--------------------------------------------------
--------------------------------------------------

type Msg  
    = SetRefreshRate String
    | SetSelectedStream SelectedStreamType
    | SetURL String
    | ParseStreamData (Result Http.Error String)
    | ParseStreamList (Result Http.Error String)


update : Msg -> Model -> (Model, Cmd Msg)
update msg model =
    case msg of
        SetRefreshRate val ->
            (setRefreshRate val model, Cmd.none)

        SetSelectedStream val ->
            (setSelectedStream val model, Cmd.none)

        SetURL val ->
            (setURL val model, Cmd.none)

        ParseStreamData result ->
            (parseStreamData result model, Cmd.none)

        ParseStreamList result ->
            (parseStreamList result model, Cmd.none)



setSelectedStream : SelectedStreamType -> Model -> Model
setSelectedStream selectedStreamType model =
    let
        selectedStream = model.selectedStream

        newSelectedStream : SelectedStream
        newSelectedStream =
            case selectedStreamType of
                 SelectedStreamName val -> 
                     {selectedStream | name = val}

                 SelectedStreamKey val -> 
                     {selectedStream | key = val}

                 SelectedStreamParameter key val ->
                     {selectedStream | parameters = Dict.update key (\_ -> Just val) selectedStream.parameters}
    in
        { model | selectedStream = newSelectedStream}

setRefreshRate : String -> Model -> Model
setRefreshRate val model =
    { model | refreshRate = String.toFloat val}

setURL : String -> Model -> Model
setURL url model =
    {model | url = url}

tick : String -> Stream -> Cmd Msg
tick url stream =
    case stream of
        Stream model ->

            if model.selectedStream == emptySelectedStream then
                Cmd.none
            else
                Cmd.batch 
                [ getStreamData url model
                , portJson model
                ]


--------------------------------------------------
--------------------------------------------------
-- DEALING WITH DOWNLOADING THE AVAILABLE PUBLIC VARIABLES
--------------------------------------------------
--------------------------------------------------

getStreamList : String -> Cmd Msg
getStreamList baseURL =
    Http.get
    { url = baseURL ++ "/streams"
    , expect = Http.expectString ParseStreamList
    }

getStreamData : String -> Model -> Cmd Msg
getStreamData baseURL model =
    let
        name = model.selectedStream.name
        key  = model.selectedStream.key

        parameters : String
        parameters = 
            model.selectedStream.parameters
            |> Dict.toList
            |> List.map (\a -> "?" ++ (Tuple.first a) ++ "=" ++ (Tuple.second a))
            |> String.concat

    in
        Http.get
        { url =  (String.join "/" [baseURL,"streams",name,key]) ++ parameters
        , expect = Http.expectString ParseStreamData
        }


streamInfoDecoder : Json.Decode.Decoder StreamInfo
streamInfoDecoder =
   Json.Decode.succeed StreamInfo
   |> Json.Decode.Pipeline.required "name" Json.Decode.string
   |> Json.Decode.Pipeline.required "keys" (Json.Decode.list Json.Decode.string)
   |> Json.Decode.Pipeline.required "parameters" (Json.Decode.list Json.Decode.string)

streamListDecoder : Json.Decode.Decoder StreamList
streamListDecoder =
    Json.Decode.succeed StreamList
    |> Json.Decode.Pipeline.required "streams" (Json.Decode.list streamInfoDecoder)


streamDataDecoder : Json.Decode.Decoder StreamData
streamDataDecoder =
   Json.Decode.succeed StreamData
       |> Json.Decode.Pipeline.optional "name" Json.Decode.string "No name"
       |> Json.Decode.Pipeline.required "x" (Json.Decode.list Json.Decode.float)
       |> Json.Decode.Pipeline.required "y" (Json.Decode.list Json.Decode.float)
       |> Json.Decode.Pipeline.optional "xTitle" Json.Decode.string "X axis"
       |> Json.Decode.Pipeline.optional "yTitle" Json.Decode.string "Y axis"
       |> Json.Decode.Pipeline.optional "maxID" Json.Decode.string "0-0"

setFirstStreamIfLengthOne: Model -> Model
setFirstStreamIfLengthOne model =
    if List.length model.streamList == 1 then
        case List.head model.streamList of
            Nothing -> model
            Just streamList ->
                case List.head streamList.keys of
                    Nothing -> model
                    Just streamKey ->
                        model 
                        |> setSelectedStream (SelectedStreamName streamList.name)
                        |> setSelectedStream (SelectedStreamKey streamKey)
    else
        model

parseStreamList : (Result Http.Error String) -> Model -> Model
parseStreamList result model =
    case result of
        Ok jsonText -> 
            case Json.Decode.decodeString streamListDecoder jsonText of
                Ok theData -> 
                    {model | streamList = theData.streams } 
                    |> setFirstStreamIfLengthOne
                Err e -> 
                    model |> Debug.log ("[Plot.elm] Json streamList error: " ++ (Json.Decode.errorToString e))

        Err e ->
            Debug.log ( "[Plot.elm] Parse Stream List Http Error: " ++ (httpErrorType e)) model

parseStreamData : (Result Http.Error String) -> Model -> Model
parseStreamData result model =
    case result of
        Ok jsonText -> 
            case Json.Decode.decodeString streamDataDecoder jsonText of
                Ok theData -> 
                    {model | streamData = theData } 
                Err e -> 
                    model |> Debug.log ("[Plot.elm] Json streamData error: " ++ (Json.Decode.errorToString e))

        Err e ->
            Debug.log ( "[Plot.elm] Parse Stream Data Http Error: " ++ (httpErrorType e)) model





--------------------------------------------------
--------------------------------------------------
-- JSON output to plotlyjs
--------------------------------------------------
--------------------------------------------------

-- Build a JSON structure corresponding to data component of PLotly input
-- N.B. it expects an array

plotlyJsonData : Model -> Json.Encode.Value
plotlyJsonData model =
    let
        singlePlot : StreamData -> List (String, Json.Encode.Value)
        singlePlot streamData =
            [ ("x",    Json.Encode.list Json.Encode.float streamData.x)
            , ("y",    Json.Encode.list Json.Encode.float streamData.y)
            , ("type", Json.Encode.string "scatter")
            , ("mode", Json.Encode.string "markers")
            , ("name", Json.Encode.string streamData.name)
            , ("hoverinfo", Json.Encode.string "skip")
            ] 

    in
        singlePlot model.streamData
        |> List.singleton
        |> Json.Encode.list Json.Encode.object 


plotlyJsonLayout : Model -> Json.Encode.Value
plotlyJsonLayout model =
    let
        xAxis : Json.Encode.Value
        xAxis = 
            [("title", Json.Encode.string model.streamData.xTitle)
            ,("showgrid", Json.Encode.bool True)
            ,("zeroline", Json.Encode.bool True)
            ]
            |> Json.Encode.object

        yAxis : Json.Encode.Value
        yAxis = 
            [("title", Json.Encode.string model.streamData.yTitle)
            ,("showgrid", Json.Encode.bool True)
            ,("zeroline", Json.Encode.bool True)
            ,("range", Json.Encode.list Json.Encode.float [0,2000])
            ]
            |> Json.Encode.object
    in
        [ ("title", Json.Encode.string "Data visualization")
        , ("xaxis", xAxis)
        , ("yaxis", yAxis)
        ]
    |> Json.Encode.object


--------------------------------------------------
--------------------------------------------------
-- View
--------------------------------------------------
--------------------------------------------------

view : Model -> Html Msg
view model =
    main_ []
    [ displayContents model
    ]

displayContents : Model -> Html Msg
displayContents model =
    div [class "section"] 
    [ div [class "container"]
      [ div [class "columns is-tablet"] 
        [ div [class "column container box is-one-third"]
          [ displayModelParameters model
          , displayStreamParameters model
          ]
        , div [class "column container box is-two-thirds"]
          [ displayFigure model
          ]
        ]
      ]
    ]

displayModelParameters : Model -> Html Msg
displayModelParameters model =
    div [class "field"]
    [ div [class "control"]
      [ label [class "label"] [text "Set figure refresh rate"]
      , input 
        [ class "input"
        , attribute "type" "number"
        , onInput SetRefreshRate
        , value ((Maybe.withDefault 0 model.refreshRate) |> String.fromFloat)
        ] []
      , p [class "help"] [text "Refresh rate (ms) for querying REST server to get fresh data."]
      ]
    ]

      

displayStreamParameters : Model -> Html Msg
displayStreamParameters model =
    let
        -- Find the streamList entry that matches the currently selected name
        -- Unwrap it from a Maybe, then convert the list of keys to a select
        keys : Html Msg
        keys =
            List.filter (\a -> a.name == model.selectedStream.name) model.streamList
            |> List.head
            |> Maybe.withDefault emptyStreamInfo
            |> .keys
            |> List.map (\n -> option [] [text n])
            |> select [onInput SelectedStreamKey |> Html.Attributes.map SetSelectedStream] 

        parameters : Html Msg
        parameters =
            let
                singleParameter : String -> Html Msg
                singleParameter name =
                    div [class "field"]
                    [ label [class "label"] [text name]
                    , div [class "control"]
                      [ input 
                        [ class "input"
                        , onInput (SelectedStreamParameter name) |> Html.Attributes.map SetSelectedStream
                        , value (Dict.get name model.selectedStream.parameters |> Maybe.withDefault "")
                        ] []
                      ]
                    ]
            in
                List.filter (\a -> a.name == model.selectedStream.name) model.streamList
                |> List.head
                |> Maybe.withDefault emptyStreamInfo
                |> .parameters
                |> List.map singleParameter 
                |> div [] 


    in
        div [] 
        [ div [class "field"]
          [ label [class "label"] [text "Parameter to stream"]
          , div [class "control"]
            [ div [class "select"]
              [ select 
                  [onInput SelectedStreamName |> Html.Attributes.map SetSelectedStream] 
                  <| (List.map (\n -> option [] [text (n.name)]) model.streamList)
              ]
              , p [class "help"] [text "Select parameter, based on command: xrange Parameter ... "]
            ]
          ]
        , div [class "field"]
          [ label [class "label"] [text "Key to stream"]
          , div [class "control"]
            [ div [class "select"] [ keys ]
            ]
          , p [class "help"] [text "Select key, based on command: xrange Parameter key ... "]
          ]
        , parameters
        ]



displayFigure : Model -> Html Msg
displayFigure model =
    div [id "plotly-div"] []

--------------------------------------------------
--------------------------------------------------
-- Helpers
--------------------------------------------------
--------------------------------------------------

httpErrorType errorType =
    case errorType of
        Http.BadUrl str ->
            "Bad URL error: " ++ str
        Http.Timeout ->
            "Network timeout error"
        Http.NetworkError ->
            "Unspecified Network error"
        Http.BadStatus val ->
            "Bad status error: " ++ (String.fromInt val)
        Http.BadBody str ->
            "Bad body error: " ++ str
