{-

Main function for interacting with the real-time rig
David Brandman

The goal of this code is to provide an interface with the user interacting with the real-time system.
Elm uses a model-view-controller architecture. The model is the type alias Model, the view is the view function, and the controller is the logic in update

Here, the idea is that Main's Model will contain a series of encapsulated models from each of the different types of views possible. For instance, the logic of how to handle the viewing of live Streams will be sent to the Stream code.



-}

module Main exposing (..)

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

-- Subscription depends on which tab we're currently looking at
-- TabStream: Query the database every getRefreshRate 

subscriptions : Model -> Sub Msg
subscriptions model =
    case model.tab of
        TabStream -> 
            case (Stream.getRefreshRate model.stream) of
                Nothing -> Sub.none
                Just val -> Time.every val Tick
        _ ->
            Sub.none
            

--------------------------------------------------
-- MODEL and INIT
--------------------------------------------------

-- Contains a list of tabs that the user can select from

type Tab =
      TabStream
    | TabYaml

type alias Model =
    { tab        : Tab    -- Which tab is currently being presented to the user
    , stream     : Stream -- Module for plotting streaming variables
    , yaml       : Yaml   -- Module for inspecting yaml parameters
    , burgerFlag : Bool   -- Is the burger expanded
    }

emptyModel : Model
emptyModel =
    { tab        = TabYaml
    , stream     = Stream.initializeStream
    , yaml       = Yaml.initializeYaml
    , burgerFlag = False
    }


init : () -> (Model, Cmd Msg)
init _ =
    (emptyModel, runCommand emptyModel.tab)

runCommand : Tab -> Cmd Msg
runCommand tab = 
    case tab of
        TabStream -> Stream.initializeStreamCommand |> Cmd.map SetStream
        TabYaml   -> Yaml.initializeYamlCommand     |> Cmd.map SetYaml

--------------------------------------------------
-- UPDATE
--------------------------------------------------

type Msg = 
      SetStream Stream.Msg
    | SetYaml Yaml.Msg
    | SetTab Tab
    | Tick Time.Posix
    | ToggleBurger
    | PostYamlCommand Yaml.Msg


update : Msg -> Model -> (Model, Cmd Msg)
update msg model =
    case msg of
        SetStream subMsg -> 
            (setStream subMsg model, Cmd.none)

        SetYaml subMsg ->
            (setYaml subMsg model, Yaml.runCommand subMsg |> Cmd.map PostYamlCommand)

        SetTab tab ->
            (setTab tab model, runCommand tab)

        Tick _ ->
            (model, Stream.streamTick model.stream |> Cmd.map SetStream)

        ToggleBurger ->
            (toggleBurger model, Cmd.none)

        PostYamlCommand subMsg ->
            (setYaml subMsg model, Cmd.none)

setStream : Stream.Msg -> Model -> Model
setStream subMsg model =
    {model | stream = Stream.updateStream subMsg model.stream}

setYaml : Yaml.Msg -> Model -> Model
setYaml subMsg model =
    {model | yaml = Yaml.updateYaml subMsg model.yaml}

toggleBurger : Model -> Model
toggleBurger model =
    {model | burgerFlag = not model.burgerFlag}

setTab : Tab -> Model -> Model
setTab tab model =
    {model | tab = tab, burgerFlag = False}

--------------------------------------------------
--------------------------------------------------
-- VIEW
--------------------------------------------------
--------------------------------------------------


view : Model -> Html Msg
view model =
    main_ []
    [ displayHero
    , displayBurger model
    , displayContent model
    ]
            
displayHero : Html Msg
displayHero =
    section [class "hero is-info"] 
    [ div [class "hero-body"] 
      [ div [class "container"] 
        [ h1 
          [ class "title"] 
          [ text "Realtime rig explorer" ]
        , h2 
          [class "subtitle"] 
          [ text "Version 0.1" ]
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
    case model.tab of
        TabStream -> displayStream model
        TabYaml -> displayYaml model

displayStream : Model -> Html Msg
displayStream model =
    Stream.displayStream model.stream
    |> Html.map SetStream

displayYaml : Model -> Html Msg
displayYaml model =
    Yaml.displayYaml model.yaml
    |> Html.map SetYaml

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
        TabYaml -> "Parameter inspector"


