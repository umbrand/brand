{-

Main function for interacting with the real-time rig
David Brandman

The goal of this code is to provide an interface with the user interacting with the real-time system.
Elm uses a model-view-controller architecture. The model is the type alias Model, the view is the view function, and the controller is the logic in update

Here, the idea is that Main's Model will contain a series of encapsulated models from each of the different types of views possible. For instance, the logic of how to handle the viewing of live Streams will be sent to the Stream code.



-}

port module Main exposing (..)

import Stream exposing (Stream)
import Yaml exposing (Yaml)

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

import List.Extra

import Process

--------------------------------------------------
-- PORTS and SUBSCRIPTIONS
--------------------------------------------------

-- port toJS_GridUpdate : String -> Cmd msg
port toElm_stream_newdata : (String -> msg) -> Sub msg

subscriptions : Model -> Sub Msg
subscriptions model =
    toElm_stream_newdata ParseSocketInput

--------------------------------------------------
-- MAIN
--------------------------------------------------

main =
  Browser.element
    { init          = init
    , update        = update
    , subscriptions = subscriptions
    , view          = view
    }


--------------------------------------------------
-- MODEL and INIT
--------------------------------------------------

-- Contains a list of tabs that the user can select from

type Tab =
      TabStream
    | TabYaml

type ModuleMsg =
      MsgStream Stream.Msg
    | MsgYaml   Yaml.Msg

type alias Model =
    { tab        : Tab     -- Which tab is currently being presented to the user
    , stream     : Stream  -- Module for plotting streaming variables
    , yaml       : Yaml    -- Module for viewing / changing parameters in the model
    , burgerFlag : Bool    -- Is the burger expanded
    , url        : String  -- The URL of the rest server
    }

emptyModel : Model
emptyModel =
    { tab        = TabStream
    , stream     = Stream.init
    , yaml       = Yaml.init
    , burgerFlag = False
    , url        = ""
    }


-- This is supplied during initialization! The jinja2 script provides the IP
-- in the html code, which is then passed to Main
init : String -> (Model, Cmd Msg)
init url =
    ( {emptyModel | url = url} , initCommand url emptyModel.tab)

--------------------------------------------------
-- COMMANDS
--------------------------------------------------

initCommand : String -> Tab -> Cmd Msg
initCommand url tab = 
    case tab of
        TabStream -> Stream.initCommand url |> Cmd.map MsgStream |> Cmd.map AfterModule
        TabYaml   -> Yaml.initCommand   url |> Cmd.map MsgYaml   |> Cmd.map AfterModule

command : ModuleMsg -> Model -> Cmd Msg
command moduleMsg model =
    case moduleMsg of
        MsgStream subMsg -> 
            Stream.command model.url subMsg model.stream
            |> Cmd.map MsgStream  
            |> Cmd.map AfterModule

        MsgYaml subMsg -> 
            Yaml.command model.url subMsg model.yaml
            |> Cmd.map MsgYaml  
            |> Cmd.map AfterModule
    


--------------------------------------------------
-- UPDATE
--------------------------------------------------

type Msg = 
      SetTab Tab
    | ToggleBurger
    | UpdateModule ModuleMsg
    | AfterModule ModuleMsg
    | ParseSocketInput String
    | RunCommandNow ModuleMsg


update : Msg -> Model -> (Model, Cmd Msg)
update msg model =
    case msg of
    
        UpdateModule moduleMsg ->
            (updateModule moduleMsg model, 
                Process.sleep 1
                |> Task.andThen (\_ -> Task.succeed (RunCommandNow moduleMsg))
                |> Task.perform (\_ -> (RunCommandNow moduleMsg)))

        AfterModule moduleMsg ->
            (updateModule moduleMsg model, Cmd.none)

        SetTab tab ->
            (setTab tab model, initCommand model.url tab)

        ToggleBurger ->
            (toggleBurger model, Cmd.none)

        ParseSocketInput str ->
            (parseSocketInput str model, portCommand model)

        RunCommandNow moduleMsg ->
            (model, command moduleMsg model)

updateModule : ModuleMsg -> Model -> Model
updateModule moduleMsg model =
    case moduleMsg of
        MsgStream subMsg  -> {model | stream = Stream.update subMsg model.stream}
        MsgYaml   subMsg  -> {model | yaml   = Yaml.update   subMsg model.yaml}

setTab : Tab -> Model -> Model
setTab tab model =
    {model | tab = tab, burgerFlag = False}

toggleBurger : Model -> Model
toggleBurger model =
    {model | burgerFlag = not model.burgerFlag}

parseSocketInput : String -> Model -> Model
parseSocketInput str model =
    case model.tab of
        TabStream -> {model | stream = Stream.addData str model.stream}
        _         -> model

portCommand : Model -> Cmd Msg
portCommand model =
    case model.tab of
        TabStream -> 
            Stream.portCommand model.stream 
            |> Cmd.map MsgStream
            |> Cmd.map AfterModule

        _ -> Cmd.none




--------------------------------------------------
--------------------------------------------------
-- VIEW
--------------------------------------------------
--------------------------------------------------


view : Model -> Html Msg
view model =
    main_ []
    [ displayHero model
    , displayBurger model
    , displayContent model
    ]
            
displayHero : Model -> Html Msg
displayHero model =
    section [class "hero is-info"] 
    [ div [class "hero-body"] 
      [ div [class "container"] 
        [ h1 
          [ class "title"] 
          [ text "Rig interface" ]
        , h2 
          [class "subtitle"] 
          [ text model.url ]
        ]
      ]
    ]

displayBurger : Model -> Html Msg
displayBurger model = 
    let
        displaySingleTab : Tab -> Html Msg
        displaySingleTab thisTab =
            a [ class "navbar-item", onClick (SetTab thisTab) ]
              [ text (tabString thisTab) ]

    in
        nav [ class "navbar"]
        [ div [ class "container" ]
          [ div [ class "navbar-brand" ]
            [ a [ class "navbar-item" , attribute "style" "font-weight:bold;" ]
              [ text (tabString model.tab)]
            , span [ classList [ ( "navbar-burger burger", True)
                   , ("is-active", model.burgerFlag)
                   ]
                   , onClick ToggleBurger ]
              [ span [] []
              , span [] []
              , span [] []
              ]
            ]
          , div 
            [ classList [ ("navbar-menu", True)
                        , ("is-active", model.burgerFlag) ]
            , id "navMenu" ]
            [ div [ class "navbar-end" ]
              <| List.map displaySingleTab tabList
            ]
          ]
        ]

displayContent : Model -> Html Msg
displayContent model =
    let
        displayStream = 
            Stream.display model.stream 
            |> Html.map MsgStream 
            |> Html.map UpdateModule

        displayYaml = 
            Yaml.display model.yaml 
            |> Html.map MsgYaml
            |> Html.map UpdateModule

    in
        case model.tab of
            TabStream -> displayStream
            TabYaml   -> displayYaml


--------------------------------------------------
--------------------------------------------------
-- Helpers
--------------------------------------------------
--------------------------------------------------

tabList : List Tab
tabList =
    [TabStream, TabYaml]

tabString : Tab -> String
tabString tab =
    case tab of
        TabStream -> "Streams"
        TabYaml   -> "Parameters"


-- portCommand : Cmd Msg
-- portCommand =
--     Process.sleep 1 
--     |> Task.andThen (\_ -> Task.succeed Port)
--     |> Task.perform (\_ -> Port)
