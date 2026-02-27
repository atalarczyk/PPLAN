Cel: 

Opracować oprogramowanie, które będzie wspierało tworzenie, monitorowanie i aktualizację planu kosztów wydziału (business unit).



Wymagania funkcjonalne:

- wykonywanie osobnych planów dla poszczególnych projektów

- agregacja informacji dotyczących poszczególnych projektów w jeden kompleksowy plan dla wydziału

- plan dla projektu musi zawierać:
  
  - specyfikację przewidywanych (i faktycznych) nakładów robocizny (osobodni) w rozbiciu na miesiące
  
  - specyfikację przewidywanych (i faktycznych) nakładów pracy w osobodniach dla poszczególnych osób w podziale na miesiące 
  
  - spójność obu powyższych planów 
  
  - możliwość rejestracji wniosków i płatność (faktur) i przychodów z tytułu realizacji projektu
  
  - wprowadzanie informacji w formie tabeli, w której miesiące kalendarzowe są kolumnami, a w wierszach są czynności (zadania) w rozbiciu na poszczególnych wykonawców; na przecięciu kolumn i wierszy wpisywane są wartości w osobodniach; komórki miesięcy obejmujące czas trwania poszczególnych etapów projektu powinny być zakolorowane (w ten sposób tworzy się rodzaj wykresu Gantta, na którym wprowadza się pracochłonności)
  
  - możliwość przypisania stawki kosztów w pieniądzu (np. na dzień lub na miesiąc FTE) osobno dla każdego wykonawcy
  
  - możliwość wygenerowania raportu o obciążeniu (planowanym i faktycznym) w osobodniach w poszczególnych miesiącach (kolumny) dla poszczególnych wykonawców (wiersze)
  
  - możliwość wygenerowania raportu o obciążeniu (planowanym i faktycznym) w w osobodniach w  poszczególnych miesiącach (kolumny) dla poszczególnych zadań w projekcie (wiersze)
  
  - możliwość wygenerowania raportu o kosztach w pieniądzu (planowanych i faktycznych) w poszczególnych miesiącach (kolumny) dla poszczególnych wykonawców (wiersze)
  
  - możliwość wygenerowania raportu o kosztach w pieniądzu (planowanych i faktycznych) w poszczególnych miesiącach (kolumny) dla poszczególnych zadań w projekcie (wiersze)

- poszczególne projekty oraz cały wydział powinny posiadać kokpity menedżerskie wizualizujący:
  
  - dynamikę w czasie kosztów planowanych i wykonanych (narastająco)
  
  - obciążenie w czasie (planowane i wykonane) poszczególnych wykonawców w osobodniach
  
  - realizację budżetu projektu (przychody i koszty) w czasie w pieniądzu

- logowanie się użytkowników za pomocą kont Microsoft w domienie firmy w Microsoft 365

- następujące role:
  
  - administrator (pełne prawa do edycji i konfiguracji aplikacji, w tym nadawania uprawnień użytkownikom)
  
  - edytor (pełne prawa do edycji planów, wprowadzania wykonań i generowania raportów)
  
  - widz (prawo tylko do oglądania planów i wykonań oraz generowania raportów, bez możliwości edycji)

- możliwość dodawania nowych projektów 
  
  

Wymagania pozafunkcjonalne:

- single-page web application

- baza danych: PostgreSQL

- aplikacja serwowana z serwera apache działającego na Ubuntu Linux

- obsługa przeglądarek: Chrome, Edge, Firefox

- interfejs ergonomiczny

- atrakcyjna wizualnie kolorystyka
