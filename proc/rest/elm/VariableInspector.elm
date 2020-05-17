-- RecordInspector
-- Project start: 30 March 2020

{-

This code interacts with a REST API and then allows the user to interact with the Redis server

This code is designed to query a REST API and then get a list of variables
that are publically exposed by that process
Then they can be manipulated and sent back to the process accordingly

The types are inferred based on the value part.
If value is a string --> Then it's RecordString
If value is a bool --> Then it's RecordBool
If value is a float --> Then it's RecordFloat

For Number, it can accept a two-long list that represents min and max values

For String, it can accept a list of strings, which can make up a drop-down menu


Here's what you need to change if you want to allow VariableInspector to see a new field in a variable:
1) Define the new field in the Record. For example, if you want a varible "color" to RecordFloat, just add it
2) Next, update the JSON decoder corresponding to the Record, and make it optional or required
3) Update the view so that you can do something (i.e. display it to the user, etc.)



-}
module VariableInspector exposing (..)

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

import List.Extra


url = "http://localhost:5000/ecog"

--------------------------------------------------
-- MAIN
--------------------------------------------------

main =
  Browser.element
    { init = init
    , update = update
    , subscriptions = subscriptions
    , view = view
    }

subscriptions : Model -> Sub Msg
subscriptions model =
  Sub.none

--------------------------------------------------
-- MODEL and INIT
--------------------------------------------------

type alias RecordString =
    { name        : String
    , value       : String
    , description : String
    , options     : List String
    , static      : Bool
    }

type alias RecordFloat =
    { name        : String
    , value       : Float
    , description : String
    , min         : Maybe Float
    , max         : Maybe Float
    , static      : Bool
    }

type alias RecordBool =
    { name        : String
    , value       : Bool
    , description : String
    , static      : Bool
    }

type Record = 
      WrapperString RecordString
    | WrapperFloat  RecordFloat
    | WrapperBool   RecordBool

type ConnectionState =
      ConnectionPosting Int
    | ConnectionReceivedError Int String
    | ConnectionReceivedOK Int
    | ConnectionNull

type alias PostRecordReply = 
    { name   : String
    , status : String
    }

type alias Model =
    { recordList      : List Record
    , connectionState : ConnectionState
    }

emptyRecord : Record
emptyRecord = WrapperBool  {name = "", value = False, description = "", static = False}

emptyModel : Model
emptyModel =
    { recordList      = []
    , connectionState = ConnectionNull
    }

init : () -> (Model, Cmd Msg)
init _ =
    (emptyModel, getRecordList )


--------------------------------------------------
-- UPDATE
--------------------------------------------------

type Msg = 
      ParseRecordList (Result Http.Error String)
    | UpdateRecord Int String
    | PostRecord Int
    | ParsePostRecordReply (Result Http.Error String)


update : Msg -> Model -> (Model, Cmd Msg)
update msg model =
    case msg of
        ParseRecordList result -> 
            (parseRecordList result model, Cmd.none)

        UpdateRecord ind value ->
            (setRecordValue ind value model, Cmd.none)

        ParsePostRecordReply result ->
            (parsePostRecordReply result model, Cmd.none)

        PostRecord ind ->
            (setConnectionPosting ind model, postRecord ind model )



setRecordValue : Int -> String -> Model -> Model
setRecordValue ind value model =
    
    let
        newRecord : Record
        newRecord =
            case List.Extra.getAt ind model.recordList of
                Just recordType ->
                    case recordType of
                        WrapperFloat  record -> 
                            WrapperFloat  {record | value = Maybe.withDefault record.value (String.toFloat value)}
                        WrapperBool   record -> 
                            WrapperBool   {record | value = not record.value}
                        WrapperString record -> 
                            WrapperString {record | value = value}

                Nothing ->
                    emptyRecord

    in
        {model | recordList = List.Extra.setAt ind newRecord model.recordList}


--------------------------------------------------
--------------------------------------------------
-- VIEW
--------------------------------------------------
--------------------------------------------------


view : Model -> Html Msg
view model =
    main_ []
    [ displayHero
    , displayVariableList model
    ]
            
displayHero : Html Msg
displayHero =
    section [class "hero is-info"] 
    [ div [class "hero-body"] 
      [ div [class "container"] 
        [ h1 
          [ class "title"] 
          [ text "ECoG" ]
        , h2 
          [class "subtitle"] 
          [ text "Version 0.1" ]
        ]
      ]
    ]


displayVariableList : Model -> Html Msg
displayVariableList model =
    let
        showRecord : Int -> Record -> Html Msg
        showRecord ind record =
            case record of
                WrapperFloat r  -> displayFloatRecord ind r
                WrapperString r -> displayStringRecord ind r
                WrapperBool r   -> displayBoolRecord ind r


        buttonClass : Int -> String
        buttonClass ind =
            case  model.connectionState of
                ConnectionPosting postingInd -> 
                    if postingInd == ind then "button is-loading" else "button"
                _ -> "button"


        showPostResponse : Int -> String
        showPostResponse ind =
            case model.connectionState of 
                ConnectionReceivedOK postingInd -> 
                    if postingInd == ind then "Received: OK" else ""
                ConnectionReceivedError postingInd str -> 
                    if postingInd == ind then ("Error: " ++ str) else ""
                _ -> ""

        entryRow : Int -> Record -> Html Msg
        entryRow ind record =
            div [class "column container box is-full-mobile"]
            [ div [class "field"]
              [ label [class "label"] [text (getName record)]
              , div [class "control"] [showRecord ind record ] 
              , p [class "help"] [text (getDescription record)]
              , button 
                [ class (buttonClass ind)
                , onClick (PostRecord ind)
                , Html.Attributes.disabled (getStatic record)
                , id ("PostButton" ++ (String.fromInt ind))] 
                [text "Submit"]
              , div [] [text (showPostResponse ind)]
              ]
            ] 

    in
        div [class "section"]
        [ div [class "container"] 
          [ div [class "columns is-desktop"] 
          <| List.map2 entryRow
                 (List.range 0 (List.length model.recordList))
                 model.recordList

          ]
        ]



displayFloatRecord : Int -> RecordFloat -> Html Msg
displayFloatRecord ind record =
    let
        floatValue : String
        floatValue = String.fromFloat record.value

        isMinOK : Bool
        isMinOK =
            case record.min of
                Nothing -> True
                Just val -> val <= record.value

        isMaxOK : Bool
        isMaxOK =
            case record.max of
                Nothing -> True
                Just val -> val >= record.value

        inputClass : String
        inputClass =
            if isMinOK && isMaxOK then
                "input"
            else 
                "input is-danger"
    
        showMin : String
        showMin =
            case record.min of
                Nothing -> ""
                Just val -> "Minimum: " ++ (String.fromFloat val) ++ "    "

        showMax : String
        showMax =
            case record.max of
                Nothing -> ""
                Just val -> "Maximum: " ++ (String.fromFloat val)

    in
        div []
        [ input 
          [ class inputClass
          , value floatValue
          , Html.Attributes.readonly (record.static)
          , onInput (UpdateRecord ind)] [text floatValue]
          , p [class "help"] [text (showMin ++ showMax)]
        ]

displayStringRecord : Int -> RecordString -> Html Msg
displayStringRecord ind record =
    let
        showInput : Html Msg
        showInput =
            div []
            [ input 
              [ class "input"
              , value record.value 
              , Html.Attributes.readonly (record.static)
              ] 
              [text record.value]
            ]

        showDropdown : Html Msg
        showDropdown =
            div [class "control"]
            [ div [class "select is-info"]
              [ select [] <| (List.map (\n -> option [] [text n]) record.options)
              ]
            ]
    in
        if List.isEmpty record.options then showInput else showDropdown



displayBoolRecord : Int -> RecordBool -> Html Msg
displayBoolRecord ind record =
    let
        isOutlined : String
        isOutlined = if record.value then "button is-info" else "button is-info is-outlined" 

        classText : String
        classText = isOutlined

        inputText = boolToString record.value
    in
        div []
        [ button 
          [ class classText
          , onClick (UpdateRecord ind "")
          , Html.Attributes.disabled (record.static)
          ] [text inputText]
        ]

--------------------------------------------------
--------------------------------------------------
-- DEALING WITH DOWNLOADING THE AVAILABLE PUBLIC VARIABLES
--------------------------------------------------
--------------------------------------------------

recordDecoderString : Json.Decode.Decoder RecordString
recordDecoderString =
   Json.Decode.succeed RecordString
       |> Json.Decode.Pipeline.required "name" Json.Decode.string
       |> Json.Decode.Pipeline.required "value" Json.Decode.string
       |> Json.Decode.Pipeline.optional "description" Json.Decode.string noDescriptionText
       |> Json.Decode.Pipeline.optional "options" (Json.Decode.list Json.Decode.string) []
       |> Json.Decode.Pipeline.optional "static" Json.Decode.bool False

recordDecoderFloat : Json.Decode.Decoder RecordFloat
recordDecoderFloat =
   Json.Decode.succeed RecordFloat
       |> Json.Decode.Pipeline.required "name" Json.Decode.string
       |> Json.Decode.Pipeline.required "value" Json.Decode.float
       |> Json.Decode.Pipeline.optional "description" Json.Decode.string ""
       |> Json.Decode.Pipeline.optional "min" (Json.Decode.map Just Json.Decode.float) Nothing
       |> Json.Decode.Pipeline.optional "max" (Json.Decode.map Just Json.Decode.float) Nothing
       |> Json.Decode.Pipeline.optional "static" Json.Decode.bool False


recordDecoderBool : Json.Decode.Decoder RecordBool
recordDecoderBool =
   Json.Decode.succeed RecordBool
       |> Json.Decode.Pipeline.required "name" Json.Decode.string
       |> Json.Decode.Pipeline.required "value" Json.Decode.bool
       |> Json.Decode.Pipeline.optional "description" Json.Decode.string ""
       |> Json.Decode.Pipeline.optional "static" Json.Decode.bool False

recordDecoder : Json.Decode.Decoder (List Record)
recordDecoder =
    let
        decoderSelector : Json.Decode.Decoder Record
        decoderSelector = 
            Json.Decode.oneOf
            [ Json.Decode.map (\response -> WrapperString response) recordDecoderString
            , Json.Decode.map (\response -> WrapperFloat  response) recordDecoderFloat
            , Json.Decode.map (\response -> WrapperBool   response) recordDecoderBool
            ]
    in
        Json.Decode.list decoderSelector

getRecordList : Cmd Msg
getRecordList =
    Http.get
    { url = url
    , expect = Http.expectString ParseRecordList
    }

parseRecordList : (Result Http.Error String) -> Model -> Model
parseRecordList result model =
    case result of
        Ok jsonText -> 
            case Json.Decode.decodeString recordDecoder jsonText of
                Ok theData -> 
                    {model | recordList = Debug.log "" theData } 
                Err e -> 
                    model |> Debug.log ("[ParseRecordList] Json: " ++ (Json.Decode.errorToString e))

        Err e ->
            Debug.log ( "[ParseRecordList] Http Error: " ++ (httpErrorType e)) model

--------------------------------------------------
--------------------------------------------------
-- DEALING WITH POSTING AND RECEIVING A VARIABLE CHANGE
--------------------------------------------------
--------------------------------------------------

postRecord : Int -> Model -> Cmd Msg
postRecord ind model =
    let
        jsonName : String
        jsonName = model |> getRecord ind |> getName

        jsonValue : String
        jsonValue = model |> getRecord ind |> getValue

        recordJsonString : String
        recordJsonString =
            [ ("name" , Json.Encode.string jsonName)
            , ("value", Json.Encode.string jsonValue) 
            ]
            |> Json.Encode.object
            |> Json.Encode.encode 0
    in
        Http.post 
            { url    = url ++ "/" ++ (model |> getRecord ind |> getName)
            , body   = Http.stringBody "application/json" recordJsonString
            , expect = Http.expectString ParsePostRecordReply
            }
            |> Debug.log "IRAN"


parsePostRecordReply : (Result Http.Error String) -> Model -> Model
parsePostRecordReply result model =
    let
        connectionInd : Int
        connectionInd = getConnectionInd model

        postRecordReplyDecoder : Json.Decode.Decoder PostRecordReply
        postRecordReplyDecoder =
           Json.Decode.succeed PostRecordReply
               |> Json.Decode.Pipeline.required "name"   Json.Decode.string
               |> Json.Decode.Pipeline.required "status" Json.Decode.string
    in
        case Debug.log "In ParsePostRecordReply" result of
            Ok jsonText -> 
                case Json.Decode.decodeString postRecordReplyDecoder jsonText of
                    Ok theData -> 
                        if (Debug.log "status" theData.status ) == "OK" then
                            setConnectionReceivedOK connectionInd model
                        else
                            setConnectionReceivedError connectionInd theData.status model
                    Err e -> 
                        model 
                        |> setConnectionReceivedError connectionInd "Could not parse incoming JSON"
                        |> Debug.log ("[ParsePostRecord] Json: " ++ (Json.Decode.errorToString e))

            Err e ->
                model 
                |> setConnectionReceivedError connectionInd "Error with HTTP connection"
                |> Debug.log ( "[ParsePostRecord] Http: " ++ (httpErrorType e))

--------------------------------------------------
--------------------------------------------------
-- Helpers
--------------------------------------------------
--------------------------------------------------
noDescriptionText : String
noDescriptionText = 
    "No description provided."


setConnectionPosting : Int -> Model -> Model
setConnectionPosting ind model =
    {model | connectionState = ConnectionPosting ind}

setConnectionReceivedOK : Int -> Model -> Model
setConnectionReceivedOK ind model =
    {model | connectionState = ConnectionReceivedOK ind}

setConnectionReceivedError : Int -> String -> Model -> Model
setConnectionReceivedError ind str model =
    {model | connectionState = ConnectionReceivedError ind str}

getConnectionInd : Model -> Int
getConnectionInd model =
    case model.connectionState of
        ConnectionReceivedError ind _ -> ind
        ConnectionReceivedOK ind -> ind
        ConnectionPosting ind -> ind
        _ -> -1

getName : Record -> String
getName record =
    case record of
        WrapperFloat r  -> .name r
        WrapperString r -> .name r
        WrapperBool r   -> .name r

getDescription : Record -> String
getDescription record =
    case record of
        WrapperFloat r  -> .description r
        WrapperString r -> .description r
        WrapperBool r   -> .description r

getValue : Record -> String
getValue record = 
    case record of
        WrapperFloat r  -> (String.fromFloat r.value)
        WrapperString r -> .value r
        WrapperBool r   -> (boolToString r.value)

getStatic : Record -> Bool
getStatic record =
    case record of
        WrapperFloat r  -> .static r
        WrapperString r -> .static r
        WrapperBool r   -> .static r



getRecord : Int -> Model -> Record
getRecord ind model =
    case List.Extra.getAt ind model.recordList of
        Nothing -> emptyRecord
        Just val -> val



boolToString : Bool -> String
boolToString val =
    if val then "True" else "False"

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
