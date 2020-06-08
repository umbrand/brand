-- Runtime

module Runtime exposing (Runtime, Msg, displayRuntime, updateRuntime, initializeRuntime, initializeRuntimeCommand, runCommand, getRefreshRate, runtimeTick)

import Browser
import Browser.Dom
import Html exposing (..)
import Html.Attributes exposing ( attribute, style, src, placeholder, type_, href, rel, class, value , classList , id)
import Html.Events exposing (onClick, onInput, onCheck)

import Http

import Json.Decode
import Json.Decode.Pipeline
import Json.Encode

import Task exposing (Task)

import List.Extra


url = "http://localhost:5000"

--------------------------------------------------
-- Exported variables
--------------------------------------------------

type Runtime = Runtime Model

displayRuntime : Runtime -> Html Msg
displayRuntime runtime = 
    case runtime of
        Runtime model -> view model

initializeRuntime : Runtime
initializeRuntime =
    init ()
    |> Tuple.first
    |> Runtime

updateRuntime : Msg -> Runtime -> Runtime
updateRuntime msg runtime =
    case runtime of
        Runtime model ->
            update msg model
            |> Tuple.first
            |> Runtime

initializeRuntimeCommand : Cmd Msg
initializeRuntimeCommand =
    Task.attempt ParseProcessList getProcessInfoListTask


getRefreshRate : Runtime -> Maybe Float
getRefreshRate runtime =
    case runtime of
        Runtime model -> model.refreshRate

runCommand : Msg -> Cmd Msg
runCommand msg =
    case msg of
        SetCurrentProcess value ->
            Task.attempt ParseProcessInfo (getProcessInfoTask value)
        ParseProcessList result ->
            case result of
                Ok runtimeFileList -> 
                    case List.head runtimeFileList.modules of
                        Nothing -> Cmd.none
                        Just head -> Task.attempt ParseProcessInfo (getProcessInfoTask head)
                Err e -> Cmd.none

        _  -> Cmd.none |> Debug.log "NOTHING"


runtimeTick : Runtime -> Cmd Msg
runtimeTick runtime =
    case runtime of
        Runtime model -> 
            if model.currentProcess == "" then
                Cmd.none
            else
                Task.attempt ParseProcessInfo <| getProcessInfoTask (model.currentProcess)
        



--------------------------------------------------
-- MAIN and GETS
--------------------------------------------------

main =
  Browser.element
    { init          = init
    , update        = update
    , subscriptions = subscriptions
    , view          = view
    }

subscriptions : Model -> Sub Msg
subscriptions model =
  Sub.none

getProcessInfoTask : String -> Task Http.Error ProcessInfo
getProcessInfoTask currentProcess =
    Http.task
        { method = "GET"
        , headers = []
        , url = url ++ "/runtimes/" ++ currentProcess
        , body = Http.emptyBody
        , resolver = Http.stringResolver <| handleJsonResponse <| processInfoDecoder
        , timeout = Nothing
        }

getProcessInfoListTask : Task Http.Error ProcessList
getProcessInfoListTask =
    Http.task
        { method = "GET"
        , headers = []
        , url = url ++ "/runtimes"
        , body = Http.emptyBody
        , resolver = Http.stringResolver <| handleJsonResponse <| processListDecoder 
        , timeout = Nothing
        }

--------------------------------------------------
-- MODEL and INIT
--------------------------------------------------

type alias ProcessInfo =
    { name        : String
    , length      : Int
    , mean        : Float
    , std         : Float
    }

type alias ProcessList =
    { modules : List String
    }

type alias Model =
    { processList     : ProcessList
    , processInfo     : ProcessInfo
    , currentProcess  : String
    , refreshRate     : Maybe Float
    }

emptyProcessInfo : ProcessInfo
emptyProcessInfo = 
    { name        = ""
    , length      = 0
    , mean        = 0.0
    , std         = 0.0
    }

emptyModel : Model
emptyModel =
    { processList    = {modules = [] }
    , processInfo    = emptyProcessInfo
    , currentProcess = ""
    , refreshRate    = Just 1000.0
    }

init : () -> (Model, Cmd Msg)
init _ =
    (emptyModel, Cmd.none)


--------------------------------------------------
-- UPDATE
--------------------------------------------------

type Msg = 
      ParseProcessInfo (Result Http.Error ProcessInfo)
    | ParseProcessList (Result Http.Error ProcessList)
    | SetCurrentProcess String


update : Msg -> Model -> (Model, Cmd Msg)
update msg model =
    case msg of
        ParseProcessInfo result -> 
            (parseProcessInfo result model, Cmd.none)

        ParseProcessList result -> 
            (parseProcessList result model, Cmd.none)

        SetCurrentProcess value ->
            (setCurrentProcess value model, Cmd.none)

parseProcessInfo : (Result Http.Error ProcessInfo) -> Model -> Model
parseProcessInfo result model =
    case result of
        Ok jsonText -> 
            {model | processInfo = jsonText}
        Err e -> 
            Debug.log ("[ParseProcessInfo] Json: " ++ (httpErrorType e)) model


parseProcessList : (Result Http.Error ProcessList) -> Model -> Model
parseProcessList result model =
    case result of
        Ok jsonText -> 
            {model | processList = jsonText}
            |> setFirstCurrentProcessIfEmpty

        Err e ->
            Debug.log ( "[ParseProcessList] Http Error: " ++ (httpErrorType e)) model

setCurrentProcess : String -> Model -> Model
setCurrentProcess val model =
    {model | currentProcess = val}

setFirstCurrentProcessIfEmpty : Model -> Model
setFirstCurrentProcessIfEmpty model =
    if model.currentProcess == "" then
        model
        |> setCurrentProcess (Maybe.withDefault "" (List.head model.processList.modules))
    else
        model


--------------------------------------------------
--------------------------------------------------
-- VIEW
--------------------------------------------------
--------------------------------------------------


view : Model -> Html Msg
view model =
    main_ []
    [ displayProcessListDrowndown model
    , displayProcessRuntime model
    ]

displayProcessListDrowndown : Model -> Html Msg
displayProcessListDrowndown model =
    div [class "section"]
    [ div [class "container box"]
      [ select [onInput SetCurrentProcess] <| List.map (\n -> option [] [text n]) model.processList.modules]
    ]


displayProcessRuntime : Model -> Html Msg
displayProcessRuntime model =
    div [class "section"]
    [ div [class "container"] 
      [ article [class "message"]
        [ div [class "message-header"] 
          [ p [] [text model.processInfo.name]
          ]
        , div [class "message-body"]
          -- [ p [] [text <| "Number of cycles: " ++ (String.fromInt model.processInfo.length )]
          -- , p [] [text <| "Mean execution: " ++ (String.fromFloat model.processInfo.mean )]
          -- , p [] [text <| "Std execution: " ++ (String.fromFloat model.processInfo.std )]
          [ p [] [text <| "Number of cycles analyzed: " ++ (String.fromInt model.processInfo.length )]
          , p [] [text <| "Mean execution (ms): " ++ (fromFloatWithDecimals model.processInfo.mean 3 )]
          , p [] [text <| "Std execution (ms): " ++ (fromFloatWithDecimals model.processInfo.std 3 )]
          ]
        ]
      ]
    ]



--------------------------------------------------
--------------------------------------------------
-- DEALING WITH DOWNLOADING THE AVAILABLE PUBLIC VARIABLES
--------------------------------------------------
--------------------------------------------------

processInfoDecoder : Json.Decode.Decoder ProcessInfo
processInfoDecoder =
   Json.Decode.succeed ProcessInfo
       |> Json.Decode.Pipeline.requiredAt ["data", "name"] Json.Decode.string
       |> Json.Decode.Pipeline.requiredAt ["data", "length"] Json.Decode.int
       |> Json.Decode.Pipeline.requiredAt ["data", "mean"] Json.Decode.float
       |> Json.Decode.Pipeline.requiredAt ["data", "std"] Json.Decode.float

processListDecoder : Json.Decode.Decoder ProcessList
processListDecoder =
    Json.Decode.succeed ProcessList
        |> Json.Decode.Pipeline.optional "runtimes" (Json.Decode.list Json.Decode.string) ["BLAH"]

--------------------------------------------------
--------------------------------------------------
-- Helpers
--------------------------------------------------
--------------------------------------------------

httpErrorType : Http.Error -> String
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

handleJsonResponse : Json.Decode.Decoder a -> Http.Response String -> Result Http.Error a
handleJsonResponse decoder response =
    case response of
        Http.BadUrl_ theUrl ->
            Err (Http.BadUrl theUrl)

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

fromFloatWithDecimals : Float -> Int -> String
fromFloatWithDecimals no decimals =
    (no * (toFloat (10 ^ decimals)))
        |> round
        |> toFloat
        |> (\n -> n / (toFloat (10 ^ decimals)))
        |> String.fromFloat

