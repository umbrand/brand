module Main exposing (..)

import Stream exposing (Stream)

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

subscriptions : Model -> Sub Msg
subscriptions model =
    case model.tab of
        TabStream -> 
            case (Stream.getRefreshRate model.stream) of
                Nothing -> Sub.none
                Just val -> Time.every val Tick
            

--------------------------------------------------
-- MODEL and INIT
--------------------------------------------------

type Tab =
    TabStream

type alias Model =
    { tab        : Tab
    , stream     : Stream
    , burgerFlag : Bool
    }

emptyModel : Model
emptyModel =
    { tab        = TabStream
    , stream     = Stream.initializeStream
    , burgerFlag = False
    }


init : () -> (Model, Cmd Msg)
init _ =
    (emptyModel, Cmd.batch [Stream.initializeStreamCommand] |> Cmd.map SetStream)


--------------------------------------------------
-- UPDATE
--------------------------------------------------

type Msg = 
      SetStream Stream.Msg
    | SetTab Tab
    | Tick Time.Posix
    | ToggleBurger


update : Msg -> Model -> (Model, Cmd Msg)
update msg model =
    case msg of
        SetStream subMsg -> 
            (setStream subMsg model, Cmd.none)

        SetTab tab ->
            (setTab tab model, Cmd.none)

        Tick _ ->
            (model, Stream.streamTick model.stream |> Cmd.map SetStream)

        ToggleBurger ->
            (toggleBurger model, Cmd.none)

setStream : Stream.Msg -> Model -> Model
setStream subMsg model =
    {model | stream = Stream.updateStream subMsg model.stream}

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

displayStream : Model -> Html Msg
displayStream model =
    Stream.displayStream model.stream
    |> Html.map SetStream

--------------------------------------------------
--------------------------------------------------
-- Helpers
--------------------------------------------------
--------------------------------------------------

tabList : List Tab
tabList =
    [TabStream]

tabString : Tab -> String
tabString tab =
    case tab of
        TabStream -> "Streams"

