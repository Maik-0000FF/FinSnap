<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="de" sourcelanguage="en">
<context>
    <name>App::Property</name>
    <message>
        <location filename="../feature.py" line="131"/>
        <source>Slicer</source>
        <translation>Slicer</translation>
    </message>
    <message>
        <location filename="../feature.py" line="132"/>
        <source>Connection</source>
        <translation>Verbindung</translation>
    </message>
    <message>
        <location filename="../feature.py" line="133"/>
        <source>Tines</source>
        <translation>Zinken</translation>
    </message>
    <message>
        <location filename="../feature.py" line="134"/>
        <source>Fin</source>
        <translation>Finne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="135"/>
        <source>Placement of fins</source>
        <translation>Lage der Finnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="136"/>
        <source>Foot</source>
        <translation>Fuß</translation>
    </message>
    <message>
        <location filename="../feature.py" line="137"/>
        <source>Counter fin</source>
        <translation>Gegenfinne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="138"/>
        <source>Source</source>
        <translation>Quelle</translation>
    </message>
    <message>
        <location filename="../feature.py" line="139"/>
        <source>Result</source>
        <translation>Ergebnis</translation>
    </message>
    <message>
        <location filename="../feature.py" line="224"/>
        <source>Nozzle diameter of the print profile</source>
        <translation>Düsendurchmesser im Druckprofil</translation>
    </message>
    <message>
        <location filename="../feature.py" line="232"/>
        <source>Layer height of the print profile</source>
        <translation>Schichthöhe im Druckprofil</translation>
    </message>
    <message>
        <location filename="../feature.py" line="236"/>
        <source>Height of the first layer</source>
        <translation>Höhe der ersten Schicht</translation>
    </message>
    <message>
        <location filename="../feature.py" line="245"/>
        <source>separate: fins are their own object and only touch the part; merged: fins and part become one body</source>
        <translation>getrennt: die Finnen sind ein eigenes Objekt und berühren das Teil nur; verbunden: Finnen und Teil werden ein Körper</translation>
    </message>
    <message>
        <location filename="../feature.py" line="256"/>
        <source>Distance between the end of a tine and the face, along the face normal; 0 = the tine touches the face. More leaves fainter marks, too much and the tine does not hold: find the value by a test print.</source>
        <translation>Abstand zwischen dem Ende einer Zinke und der Fläche, senkrecht zur Fläche gemessen; 0 = die Zinke berührt die Fläche. Mehr hinterlässt schwächere Spuren, zu viel und die Zinke hält nicht: den Wert mit einem Probedruck finden.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="263"/>
        <source>Vertical distance between tines, at least the tine height plus one layer</source>
        <translation>Senkrechter Abstand der Zinken, mindestens die Zinkenhöhe plus eine Schicht</translation>
    </message>
    <message>
        <location filename="../feature.py" line="228"/>
        <source>Bead width, the extrusion width of the outer perimeter</source>
        <translation>Raupenbreite, die Extrusionsbreite der Außenwand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="240"/>
        <source>Width of the brim the slicer prints round the part and the fins on the bed, 0 without. Check stability counts it as part of the footprint.</source>
        <translation>Breite des Brims, den der Slicer um Teil und Finnen auf dem Bett druckt, 0 ohne. Standfestigkeit prüfen zählt ihn zur Standfläche.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="251"/>
        <source>Gap between fin and face that the tines reach across, along the face normal; a tine clearance adds to it</source>
        <translation>Spalt zwischen Finne und Fläche, über den die Zinken reichen, senkrecht zur Fläche gemessen; ein Abstand Zinke zum Teil kommt hinzu</translation>
    </message>
    <message>
        <location filename="../feature.py" line="268"/>
        <source>Start the tine grid anew at the lower edge of the face under each fin and above every interruption it reaches over, so a short face or one above a hole still gets tines; off, one grid counts from the bed for every fin</source>
        <translation>Zinkenraster an der Unterkante der Fläche unter jeder Finne und über jeder Unterbrechung, über die sie hinwegreicht, neu beginnen, damit auch eine kurze Fläche oder eine über einem Loch Zinken bekommt; aus: ein Raster vom Bett aus für alle Finnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="275"/>
        <source>Height of the lowest tine above the bed, 0 = on the top of the foot</source>
        <translation>Höhe der untersten Zinke über dem Bett, 0 = auf der Oberkante des Fußes</translation>
    </message>
    <message>
        <location filename="../feature.py" line="279"/>
        <source>Tine height in layers</source>
        <translation>Höhe einer Zinke in Schichten</translation>
    </message>
    <message>
        <location filename="../feature.py" line="283"/>
        <source>Tine width in beads</source>
        <translation>Breite einer Zinke in Raupen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="287"/>
        <source>Number of tines per fin, 0 = as many as fit</source>
        <translation>Zinken je Finne, 0 = so viele wie passen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="291"/>
        <source>Wall thickness of a fin, 0 = from its height</source>
        <translation>Wandstärke einer Finne, 0 = aus ihrer Höhe</translation>
    </message>
    <message>
        <location filename="../feature.py" line="295"/>
        <source>Height of the fins, 0 = top of the highest tine. A lower value leaves out the tines above it; the fins reach at most to just below the top of the face.</source>
        <translation>Höhe der Finnen, 0 = Oberkante der höchsten Zinke. Ein kleinerer Wert lässt die Zinken darüber weg; die Finnen reichen höchstens bis knapp unter die Oberkante der Fläche.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="301"/>
        <source>Width of the flat top of a fin</source>
        <translation>Breite der flachen Oberseite einer Finne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="305"/>
        <source>auto: by face length; center: one fin; ends: two fins; corners: two fins on the face ends, each tine whole on the face and flush with its end, so the tine marks merge with the edges; the fin reaches a little past the end; left corner, right corner: one such fin on that end, left and right as seen from outside, looking at the face; distributed: FinCount fins</source>
        <translation>automatisch: nach Flächenlänge; mittig: eine Finne; Enden: zwei Finnen; Ecken: zwei Finnen an den Flächenenden, jede Zinke liegt ganz auf der Fläche und schließt bündig mit ihrem Ende ab, so verschwinden die Spuren der Zinken in den Kanten; die Finne ragt etwas über das Ende hinaus; linke Ecke, rechte Ecke: eine solche Finne an diesem Ende, links und rechts von außen auf die Fläche gesehen; verteilt: Anzahl Finnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="315"/>
        <source>Number of fins for distributed placement</source>
        <translation>Anzahl der Finnen bei verteilter Lage</translation>
    </message>
    <message>
        <location filename="../feature.py" line="319"/>
        <source>Distance of the outer fins from the face ends</source>
        <translation>Abstand der äußeren Finnen von den Enden der Fläche</translation>
    </message>
    <message>
        <location filename="../feature.py" line="323"/>
        <source>Automatic placement: one fin per this much face length</source>
        <translation>Automatische Lage: eine Finne je so viel Flächenlänge</translation>
    </message>
    <message>
        <location filename="../feature.py" line="327"/>
        <source>Shape of the foot on the bed</source>
        <translation>Form des Fußes auf dem Bett</translation>
    </message>
    <message>
        <location filename="../feature.py" line="331"/>
        <source>Height of the foot, rounded to whole layers</source>
        <translation>Höhe des Fußes, auf ganze Schichten gerundet</translation>
    </message>
    <message>
        <location filename="../feature.py" line="335"/>
        <source>How far the foot reaches past the outer end of the fin</source>
        <translation>Wie weit der Fuß über das äußere Ende der Finne hinausreicht</translation>
    </message>
    <message>
        <location filename="../feature.py" line="339"/>
        <source>Foot width as a share of its length</source>
        <translation>Breite des Fußes als Anteil seiner Länge</translation>
    </message>
    <message>
        <location filename="../feature.py" line="343"/>
        <source>Half width of the foot, 0 = from FootWidthRatio</source>
        <translation>Halbe Breite des Fußes, 0 = aus dem Breitenanteil</translation>
    </message>
    <message>
        <location filename="../feature.py" line="347"/>
        <source>Tines of the counter fin, 0 = as many as the main fin. The counter fin only has to stop the part from tipping over, so it may be smaller.</source>
        <translation>Zinken der Gegenfinne, 0 = so viele wie die Hauptfinne. Die Gegenfinne muss nur das Umkippen des Teils verhindern und darf deshalb kleiner sein.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="400"/>
        <source>Part and the face the fins support</source>
        <translation>Teil und die Fläche, die die Finnen stützen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="402"/>
        <source>Outermost container of the part, so moving it rebuilds the fins</source>
        <translation>Äußerster Container des Teils, damit ein Verschieben die Finnen neu berechnet</translation>
    </message>
    <message>
        <location filename="../feature.py" line="407"/>
        <source>Optional face on the opposite side for a small counter fin</source>
        <translation>Optionale Fläche auf der Gegenseite für eine kleine Gegenfinne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="422"/>
        <source>Faces of the part that overhang too flatly and carry no fins</source>
        <translation>Flächen des Teils, die zu flach überhängen und keine Finnen tragen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="428"/>
        <source>Where the part would start printing in the air</source>
        <translation>Wo das Teil in der Luft zu drucken beginnen würde</translation>
    </message>
    <message>
        <location filename="../orient.py" line="138"/>
        <source>FinSnap</source>
        <translation>FinSnap</translation>
    </message>
    <message>
        <location filename="../orient.py" line="139"/>
        <source>Placement before Stand on edge, restored by Lay flat again</source>
        <translation>Platzierung vor Auf Kante stellen, wiederhergestellt von Wieder flach legen</translation>
    </message>
    <message>
        <location filename="../check.py" line="41"/>
        <source>Check</source>
        <translation>Prüfung</translation>
    </message>
    <message>
        <location filename="../check.py" line="42"/>
        <source>Shown</source>
        <translation>Anzeige</translation>
    </message>
    <message>
        <location filename="../check.py" line="49"/>
        <source>The part checked</source>
        <translation>Das geprüfte Teil</translation>
    </message>
    <message>
        <location filename="../check.py" line="52"/>
        <source>The fins of the part checked</source>
        <translation>Die Finnen des geprüften Teils</translation>
    </message>
    <message>
        <location filename="../check.py" line="56"/>
        <source>What was checked</source>
        <translation>Was geprüft wurde</translation>
    </message>
    <message>
        <location filename="../check.py" line="58"/>
        <source>What the check found</source>
        <translation>Was die Prüfung ergab</translation>
    </message>
    <message>
        <location filename="../check.py" line="61"/>
        <source>The part, its place or its fins changed since: double-click to check again</source>
        <translation>Das Teil, seine Lage oder seine Finnen haben sich seitdem geändert: zum erneuten Prüfen doppelklicken</translation>
    </message>
</context>
<context>
    <name>FinSnap</name>
    <message>
        <location filename="../commands.py" line="49"/>
        <source>3MF files (*.3mf)</source>
        <translation>3MF-Dateien (*.3mf)</translation>
    </message>
    <message>
        <location filename="../commands.py" line="53"/>
        <source>Select a part, or its fins, to check whether it stays standing while it is printed.</source>
        <translation>Wähle ein Teil oder seine Finnen aus, um zu prüfen, ob es während des Drucks stehen bleibt.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="56"/>
        <source>Another task panel is open. Close it first, then make the fins again.</source>
        <translation>Ein anderes Aufgabenfenster ist offen. Schließe es zuerst und erzeuge die Finnen dann erneut.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="255"/>
        <source>Remove fin</source>
        <translation>Finne entfernen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="338"/>
        <source>Select one edge of the part, and the face of that edge that is to lie on the bed; or a face alone, a chamfer or a fillet; or the two faces beside it.</source>
        <translation>Wähle eine Kante des Teils und die Fläche dieser Kante, die auf dem Bett liegen soll; oder eine Fläche allein, eine Fase oder eine Verrundung; oder die beiden Flächen daneben.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="358"/>
        <location filename="../commands.py" line="369"/>
        <source>Stand on edge</source>
        <translation>Auf Kante stellen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="359"/>
        <source>Tilt angle (degrees):</source>
        <translation>Neigungswinkel (Grad):</translation>
    </message>
    <message>
        <location filename="../commands.py" line="427"/>
        <source>%d faces overhang flatter than %.0f degrees from the bed and are selected: they need fins or support.</source>
        <translation>%d Flächen hängen flacher als %.0f Grad zur Bettebene über und sind ausgewählt: sie brauchen Finnen oder Stützen.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="486"/>
        <source>Lay flat again</source>
        <translation>Wieder flach legen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="505"/>
        <source>Delete the fins of the part as well? No keeps them, moved along with the part, and rebuilds them once it is moved again, for example stood on its edge.</source>
        <translation>Die Finnen des Teils auch löschen? Nein behält sie, mit dem Teil mitbewegt, und baut sie neu, sobald es wieder bewegt wird, etwa auf die Kante gestellt.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="546"/>
        <source>Select an edge or a face of one part.</source>
        <translation>Wähle eine Kante oder eine Fläche eines Teils.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="902"/>
        <source>nothing to export: the parts of %s lie flat; stand them on their edge again</source>
        <translation>nichts zu exportieren: die Teile von %s liegen flach; stelle sie wieder auf die Kante</translation>
    </message>
    <message>
        <location filename="../commands.py" line="1017"/>
        <source>Left out, as their part lies flat: %s. Stand it on its edge again to export these fins.</source>
        <translation>Ausgelassen, weil ihr Teil flach liegt: %s. Stelle es wieder auf die Kante, um diese Finnen zu exportieren.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="471"/>
        <source>The selection was not stood on an edge with Stand on edge.</source>
        <translation>Die Auswahl wurde nicht mit Auf Kante stellen aufgestellt.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="51"/>
        <source>STEP files (*.step *.stp)</source>
        <translation>STEP-Dateien (*.step *.stp)</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1476"/>
        <source>This edge does not lie on the bed, and its faces do not meet at a right angle. Use Stand on edge with the edge and the face that is to lie on the bed, then Add fins.</source>
        <translation>Diese Kante liegt nicht auf dem Bett, und ihre Flächen treffen sich nicht im rechten Winkel. Nimm „Auf Kante stellen“ mit der Kante und der Fläche, die auf das Bett soll, und danach „Finnen hinzufügen“.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="563"/>
        <source>Quick fins</source>
        <translation>Schnelle Finnen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="777"/>
        <source>Select one face to support, or two faces for a counter fin.</source>
        <translation>Eine Fläche zum Stützen auswählen, oder zwei Flächen für eine Gegenfinne.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="782"/>
        <source>Add fins</source>
        <translation>Finnen hinzufügen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="817"/>
        <source>Select one fin object, and optionally one face of its part.</source>
        <translation>Ein Finnen-Objekt auswählen, optional dazu eine Fläche seines Teils.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="820"/>
        <source>The face for the counter fin has to belong to the part the fins stand under.</source>
        <translation>Die Fläche für die Gegenfinne muss zu dem Teil gehören, unter dem die Finnen stehen.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="823"/>
        <location filename="../taskpanel.py" line="749"/>
        <source>Add counter fin</source>
        <translation>Gegenfinne hinzufügen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="109"/>
        <source>No counter fin on this face: %s</source>
        <translation>Keine Gegenfinne auf dieser Fläche: %s</translation>
    </message>
    <message>
        <location filename="../commands.py" line="911"/>
        <source>Mesh fineness</source>
        <translation>Netzfeinheit</translation>
    </message>
    <message>
        <location filename="../commands.py" line="919"/>
        <source>Surface deviation</source>
        <translation>Oberflächenabweichung</translation>
    </message>
    <message>
        <location filename="../commands.py" line="926"/>
        <source>Angular deviation</source>
        <translation>Winkelabweichung</translation>
    </message>
    <message>
        <location filename="../commands.py" line="928"/>
        <source>Planar faces are exported exactly; these values only affect curved surfaces.</source>
        <translation>Ebene Flächen werden exakt exportiert; diese Werte wirken nur auf gekrümmte Flächen.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="963"/>
        <source>Export 3MF</source>
        <translation>3MF exportieren</translation>
    </message>
    <message>
        <location filename="../commands.py" line="986"/>
        <source>Export STEP</source>
        <translation>STEP exportieren</translation>
    </message>
    <message>
        <location filename="../feature.py" line="172"/>
        <source>Enter the values of the print profile you will slice with. Tines and fin are sized in beads and layers of this profile.</source>
        <translation>Die Werte des Druckprofils eintragen, mit dem gesliced wird. Zinken und Finne werden in Raupen und Schichten dieses Profils bemessen.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="127"/>
        <source>The part lies flat again: the fins keep their last shape until the part is moved, for example stood on its edge again; then they are rebuilt.</source>
        <translation>Das Teil liegt wieder flach: Die Finnen behalten ihre letzte Form, bis das Teil bewegt wird, etwa wieder auf die Kante gestellt; dann werden sie neu gebaut.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="37"/>
        <source>%d faces of %s overhang flatter than %.0f degrees from the bed without fins: %s</source>
        <translation>%d Flächen von %s hängen flacher als %.0f Grad zur Bettebene über und tragen keine Finnen: %s</translation>
    </message>
    <message>
        <location filename="../feature.py" line="39"/>
        <source>%d faces of %s overhang flatter than %.0f degrees from the bed without fins, too flat to print: %s</source>
        <translation>%d Flächen von %s hängen flacher als %.0f Grad zur Bettebene über und tragen keine Finnen, zu flach zum Drucken: %s</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="57"/>
        <source>%d bridges of %s span further than %.1f mm, the longest %.1f mm: %s</source>
        <translation>%d Brücken von %s spannen weiter als %.1f mm, die längste %.1f mm: %s</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="59"/>
        <source>%d bridges of %s span further than %.1f mm, too far to print, the longest %.1f mm: %s</source>
        <translation>%d Brücken von %s spannen weiter als %.1f mm, zu weit zum Drucken, die längste %.1f mm: %s</translation>
    </message>
    <message>
        <location filename="../feature.py" line="55"/>
        <source>%d island(s): %s would start printing in the air there, on no layer of it below. Fins do not carry an island, they only keep the part from tipping over. It cannot print standing so; the islands are marked in the 3D view.</source>
        <translation>%d Insel(n): %s würde dort in der Luft zu drucken beginnen, ohne eigene Schicht darunter. Finnen tragen keine Insel, sie halten das Teil nur gegen Umkippen. So aufgestellt lässt es sich nicht drucken; die Inseln sind in der 3D-Ansicht markiert.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="84"/>
        <source>The number of fins changed, so the fins changed by hand are as planned again: removed fins are back, moved fins and fin heights of their own are undone.</source>
        <translation>Die Zahl der Finnen hat sich geändert, deshalb sind die von Hand geänderten Finnen wieder wie geplant: entfernte Finnen sind zurück, Verschiebungen und eigene Höhen sind aufgehoben.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="87"/>
        <source>The tines lie at other heights now, so fin heights of their own are undone: each fin ends at its highest tine again.</source>
        <translation>Die Zinken liegen jetzt auf anderen Höhen, deshalb sind die eigenen Finnenhöhen zurückgesetzt: jede Finne endet wieder an ihrer obersten Zinke.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="105"/>
        <source>Single fins can be removed with the separate connection only; merged into the part they have no body of their own. To delete all of them, select the fins in the tree.</source>
        <translation>Einzelne Finnen lassen sich nur mit der getrennten Verbindung entfernen; mit dem Teil verbunden haben sie keinen eigenen Körper. Um alle zu löschen, wähle die Finnen im Baum.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="111"/>
        <source>The part has no face leaning the other way that takes a counter fin. Select one yourself.</source>
        <translation>Das Teil hat keine Fläche, die sich andersherum neigt und eine Gegenfinne trägt. Wähle selbst eine aus.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="115"/>
        <source>%s is the seam between two halves of a side; select the side or its rim instead</source>
        <translation>%s ist die Naht zwischen zwei Hälften einer Seite; wähle stattdessen die Seite oder ihren Rand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="119"/>
        <source>the face the fins stand under is gone from %s: select a face for them again</source>
        <translation>die Fläche, unter der die Finnen stehen, gibt es an %s nicht mehr: wähle erneut eine Fläche für sie</translation>
    </message>
    <message>
        <location filename="../feature.py" line="122"/>
        <source>%s of the joined part matches no face of the part itself</source>
        <translation>%s des zusammengefügten Teils passt zu keiner Fläche des Teils selbst</translation>
    </message>
    <message>
        <location filename="../feature.py" line="175"/>
        <source>Separate keeps the fins a separate object that only touches the part and breaks off cleanly. Merged prints fins and part as one body. A tine clearance keeps the ends of the tines that far from the face.</source>
        <translation>Getrennt hält die Finnen als eigenes Objekt, das das Teil nur berührt und sauber abbricht. Verbunden druckt Finnen und Teil als einen Körper. Ein Abstand Zinke zum Teil hält die Enden der Zinken so weit von der Fläche fern.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="179"/>
        <source>Tines are the small horizontal contacts between fin and part. The highest tine sets the height of the fin.</source>
        <translation>Zinken sind die kleinen waagerechten Kontakte zwischen Finne und Teil. Die höchste Zinke bestimmt die Höhe der Finne.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="182"/>
        <source>0 means automatic: the thickness grows with the height, the height ends at the highest tine.</source>
        <translation>0 heißt automatisch: die Dicke wächst mit der Höhe, die Höhe endet an der höchsten Zinke.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="185"/>
        <source>Automatic places one fin per face length set below, a single fin in the centre.</source>
        <translation>Automatisch setzt eine Finne je unten eingestellter Flächenlänge, eine einzelne Finne mittig.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="188"/>
        <source>The foot holds the fin on the bed. It is narrowed automatically so that the feet of neighbouring fins never touch.</source>
        <translation>Der Fuß hält die Finne auf dem Bett. Er wird automatisch schmaler, damit sich die Füße benachbarter Finnen nie berühren.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="191"/>
        <source>A fin on the opposite face, against tipping away, as large as the main fin. It only has to stop the part from tipping over, so fewer tines are enough to make it smaller. Add it with Add counter fin, or select a second face when adding the fins.</source>
        <translation>Eine Finne auf der Gegenseite gegen Wegkippen, so groß wie die Hauptfinne. Sie muss nur das Umkippen verhindern, weniger Zinken machen sie kleiner. Mit Gegenfinne hinzufügen ergänzen, oder beim Hinzufügen der Finnen eine zweite Fläche auswählen.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="206"/>
        <source>separate, touching only</source>
        <translation>getrennt, nur berührend</translation>
    </message>
    <message>
        <location filename="../feature.py" line="207"/>
        <source>merged into the part</source>
        <translation>mit dem Teil verbunden</translation>
    </message>
    <message>
        <location filename="../feature.py" line="208"/>
        <source>automatic</source>
        <translation>automatisch</translation>
    </message>
    <message>
        <location filename="../feature.py" line="209"/>
        <source>one in the centre</source>
        <translation>eine mittig</translation>
    </message>
    <message>
        <location filename="../feature.py" line="210"/>
        <source>two at the ends</source>
        <translation>zwei an den Enden</translation>
    </message>
    <message>
        <location filename="../feature.py" line="211"/>
        <source>two on the corners</source>
        <translation>zwei auf den Ecken</translation>
    </message>
    <message>
        <location filename="../feature.py" line="212"/>
        <source>one on the left corner</source>
        <translation>eine auf der linken Ecke</translation>
    </message>
    <message>
        <location filename="../feature.py" line="213"/>
        <source>one on the right corner</source>
        <translation>eine auf der rechten Ecke</translation>
    </message>
    <message>
        <location filename="../feature.py" line="214"/>
        <source>distributed</source>
        <translation>verteilt</translation>
    </message>
    <message>
        <location filename="../feature.py" line="215"/>
        <source>oval</source>
        <translation>oval</translation>
    </message>
    <message>
        <location filename="../feature.py" line="216"/>
        <source>rectangle</source>
        <translation>rechteckig</translation>
    </message>
    <message>
        <location filename="../feature.py" line="217"/>
        <source>none</source>
        <translation>keiner</translation>
    </message>
    <message>
        <location filename="../feature.py" line="223"/>
        <source>Nozzle diameter</source>
        <translation>Düsendurchmesser</translation>
    </message>
    <message>
        <location filename="../feature.py" line="227"/>
        <source>Bead width</source>
        <translation>Raupenbreite</translation>
    </message>
    <message>
        <location filename="../feature.py" line="231"/>
        <source>Layer height</source>
        <translation>Schichthöhe</translation>
    </message>
    <message>
        <location filename="../feature.py" line="235"/>
        <source>First layer height</source>
        <translation>Höhe der ersten Schicht</translation>
    </message>
    <message>
        <location filename="../feature.py" line="239"/>
        <source>Brim width</source>
        <translation>Brim-Breite</translation>
    </message>
    <message>
        <location filename="../feature.py" line="244"/>
        <source>Connection</source>
        <translation>Verbindung</translation>
    </message>
    <message>
        <location filename="../feature.py" line="250"/>
        <source>Gap</source>
        <translation>Spalt</translation>
    </message>
    <message>
        <location filename="../feature.py" line="255"/>
        <source>Tine clearance</source>
        <translation>Abstand Zinke zum Teil</translation>
    </message>
    <message>
        <location filename="../feature.py" line="262"/>
        <source>Tine spacing</source>
        <translation>Zinkenabstand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="267"/>
        <source>Restart tines after an interruption</source>
        <translation>Zinken nach Unterbrechung neu beginnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="330"/>
        <source>Foot height</source>
        <translation>Fußhöhe</translation>
    </message>
    <message>
        <location filename="../feature.py" line="334"/>
        <source>Foot reach</source>
        <translation>Fußüberstand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="274"/>
        <source>Tine first</source>
        <translation>Erste Zinke</translation>
    </message>
    <message>
        <location filename="../feature.py" line="278"/>
        <source>Tine layers</source>
        <translation>Zinkenhöhe in Schichten</translation>
    </message>
    <message>
        <location filename="../feature.py" line="282"/>
        <source>Tine width beads</source>
        <translation>Zinkenbreite in Raupen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="286"/>
        <source>Tine count</source>
        <translation>Zinkenanzahl</translation>
    </message>
    <message>
        <location filename="../feature.py" line="290"/>
        <source>Fin thickness</source>
        <translation>Finnendicke</translation>
    </message>
    <message>
        <location filename="../feature.py" line="294"/>
        <source>Fin height</source>
        <translation>Finnenhöhe</translation>
    </message>
    <message>
        <location filename="../feature.py" line="300"/>
        <source>Top width</source>
        <translation>Breite der Oberseite</translation>
    </message>
    <message>
        <location filename="../feature.py" line="304"/>
        <source>Fin placement</source>
        <translation>Lage der Finnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="314"/>
        <source>Fin count</source>
        <translation>Anzahl Finnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="318"/>
        <source>End inset</source>
        <translation>Randabstand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="322"/>
        <source>Face length per fin</source>
        <translation>Flächenlänge je Finne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="326"/>
        <source>Foot shape</source>
        <translation>Fußform</translation>
    </message>
    <message>
        <location filename="../feature.py" line="338"/>
        <source>Foot width ratio</source>
        <translation>Breitenanteil des Fußes</translation>
    </message>
    <message>
        <location filename="../feature.py" line="342"/>
        <source>Foot half width</source>
        <translation>Halbe Fußbreite</translation>
    </message>
    <message>
        <location filename="../feature.py" line="346"/>
        <source>Counter tine count</source>
        <translation>Zinken der Gegenfinne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="358"/>
        <source>Not used without a foot.</source>
        <translation>Ohne Fuß nicht verwendet.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="361"/>
        <source>Only used with distributed placement.</source>
        <translation>Nur bei verteilter Lage verwendet.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="363"/>
        <source>Only used with automatic placement.</source>
        <translation>Nur bei automatischer Lage verwendet.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="365"/>
        <source>Not used with one fin in the centre or fins on the corners.</source>
        <translation>Nicht verwendet bei einer Finne in der Mitte oder Finnen auf den Ecken.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="371"/>
        <source>Only used while Foot half width is 0.</source>
        <translation>Nur verwendet, solange Halbe Fußbreite 0 ist.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="373"/>
        <source>Only used with a counter fin.</source>
        <translation>Nur mit Gegenfinne verwendet.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="375"/>
        <source>Not used with fins merged into the part: they need their tines on the face, or they would be loose bodies.</source>
        <translation>Nicht verwendet bei Finnen, die mit dem Teil verbunden werden: Ihre Zinken müssen auf der Fläche sitzen, sonst wären sie lose Körper.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="455"/>
        <source>no face selected on %s</source>
        <translation>keine Fläche an %s gewählt</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="64"/>
        <source>Nothing of the part stands on the bed.</source>
        <translation>Nichts von dem Teil steht auf dem Bett.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="68"/>
        <source>Stands on its own while it is printed: tipping angle at least %.1f degrees, smallest at layer %d (%.1f mm), with a tipping margin of %.1f mm; withstands %.0f mm/s² from the side.</source>
        <translation>Steht während des Drucks sicher von allein: Kippwinkel mindestens %.1f Grad, am kleinsten bei Schicht %d (%.1f mm), mit einem Kippabstand von %.1f mm; hält %.0f mm/s² von der Seite aus.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="71"/>
        <source>At risk of tipping on its own: tipping angle only %.1f degrees at layer %d (%.1f mm), with a tipping margin of %.1f mm; withstands %.0f mm/s² from the side.</source>
        <translation>Allein kippgefährdet: Kippwinkel nur %.1f Grad bei Schicht %d (%.1f mm), mit einem Kippabstand von %.1f mm; hält %.0f mm/s² von der Seite aus.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="74"/>
        <source>Tips over at layer %d (%.1f mm) while it is printed: fins under its leaning face hold it.</source>
        <translation>Kippt während des Drucks bei Schicht %d (%.1f mm) um: Finnen unter seiner geneigten Fläche halten es.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="76"/>
        <source>On its own it would tip over at layer %d (%.1f mm); its fins hold it: tipping angle at least %.1f degrees, smallest at layer %d (%.1f mm), with a tipping margin of %.1f mm; withstands %.0f mm/s² from the side.</source>
        <translation>Allein würde es bei Schicht %d (%.1f mm) umkippen; seine Finnen halten es: Kippwinkel mindestens %.1f Grad, am kleinsten bei Schicht %d (%.1f mm), mit einem Kippabstand von %.1f mm; hält %.0f mm/s² von der Seite aus.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="80"/>
        <source>On its own it would tip over at layer %d (%.1f mm); its fins hold it, but it is at risk of tipping: tipping angle only %.1f degrees at layer %d (%.1f mm), with a tipping margin of %.1f mm; withstands %.0f mm/s² from the side.</source>
        <translation>Allein würde es bei Schicht %d (%.1f mm) umkippen; seine Finnen halten es, aber es ist kippgefährdet: Kippwinkel nur %.1f Grad bei Schicht %d (%.1f mm), mit einem Kippabstand von %.1f mm; hält %.0f mm/s² von der Seite aus.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="84"/>
        <source>Tips over at layer %d (%.1f mm), before its fins hold it from their lowest tine at %.1f mm: set the first tine lower.</source>
        <translation>Kippt bei Schicht %d (%.1f mm) um, bevor seine Finnen es ab ihrer untersten Zinke bei %.1f mm halten: setze die erste Zinke tiefer.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="87"/>
        <source>Tips over at layer %d (%.1f mm), away from its fins: a counter fin on that side holds it.</source>
        <translation>Kippt bei Schicht %d (%.1f mm) von seinen Finnen weg um: eine Gegenfinne auf dieser Seite hält es.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="89"/>
        <source>Tips over at layer %d (%.1f mm) towards its fins, past their feet: a longer foot or more fins hold it.</source>
        <translation>Kippt bei Schicht %d (%.1f mm) zu seinen Finnen hin um, über ihre Füße hinaus: ein längerer Fuß oder mehr Finnen halten es.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="92"/>
        <source>Tips over at layer %d (%.1f mm), past an end of the edge it stands on.</source>
        <translation>Kippt bei Schicht %d (%.1f mm) über ein Ende der Kante um, auf der es steht.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="105"/>
        <source>Colours by height: green stands, yellow is at risk of tipping (tipping angle under %.0f degrees), red tips over from there.</source>
        <translation>Farben nach Höhe: grün steht sicher, gelb ist kippgefährdet (Kippwinkel unter %.0f Grad), rot kippt ab dort.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="888"/>
        <source>Main fin: %s</source>
        <translation>Hauptfinne: %s</translation>
    </message>
    <message>
        <location filename="../feature.py" line="847"/>
        <location filename="../feature.py" line="892"/>
        <source>Counter fin: %s</source>
        <translation>Gegenfinne: %s</translation>
    </message>
    <message>
        <location filename="../feature.py" line="125"/>
        <source>the counter fin goes under a flat face, not under the side of a cylinder or tube</source>
        <translation>die Gegenfinne gehört unter eine ebene Fläche, nicht unter die Seite eines Zylinders oder Rohrs</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="687"/>
        <source>FinSnap parameters</source>
        <translation>FinSnap-Parameter</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="182"/>
        <source>Side view</source>
        <translation>Seitenansicht</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="96"/>
        <source>Main fin</source>
        <translation>Hauptfinne</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="97"/>
        <source>Counter fin</source>
        <translation>Gegenfinne</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="166"/>
        <source>Smallest tipping angle at layer %d, %.1f mm high</source>
        <translation>Kleinster Kippwinkel bei Schicht %d, %.1f mm hoch</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="183"/>
        <source>Top view</source>
        <translation>Draufsicht</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="691"/>
        <source>Hover over a field for an explanation. Letters in brackets point to the drawings below. Every change is shown in the 3D view right away. Greyed-out fields have no effect with the current choices; their tooltip says why.</source>
        <translation>Für eine Erklärung mit der Maus über ein Feld fahren. Buchstaben in Klammern verweisen auf die Zeichnungen unten. Jede Änderung erscheint sofort in der 3D-Ansicht. Ausgegraute Felder wirken bei der aktuellen Wahl nicht; ihr Tooltip sagt, warum.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="120"/>
        <source>Edit fins</source>
        <translation>Finnen bearbeiten</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="747"/>
        <source>Remove selected fin</source>
        <translation>Gewählte Finne entfernen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="750"/>
        <source>Remove counter fin</source>
        <translation>Gegenfinne entfernen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="758"/>
        <source>The fins, the main fins from the left, then the counter fins. Pick one to put the arrows on it and select it.</source>
        <translation>Die Finnen, erst die Hauptfinnen von links, dann die Gegenfinnen. Wähle eine aus, um die Pfeile auf sie zu setzen und sie auszuwählen.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="80"/>
        <source>Place on the face</source>
        <translation>Lage auf der Fläche</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="48"/>
        <source>on</source>
        <translation>an</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="49"/>
        <source>off</source>
        <translation>aus</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="85"/>
        <source>Angle on the part</source>
        <translation>Winkel am Teil</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="90"/>
        <source>Height</source>
        <translation>Höhe</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="142"/>
        <source>%d faces overhang critically, %d too flat to print.</source>
        <translation>%d Flächen hängen kritisch über, %d zu flach zum Drucken.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="144"/>
        <source>%d bridges span critically, %d too far to print.</source>
        <translation>%d Brücken spannen kritisch weit, %d zu weit zum Drucken.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="146"/>
        <source>Quick fins found more than one way to stand the part. Click a row to stand it so; the part and its fins follow in the 3D view. Ways where the part would start printing in the air, an island, or where a face lies too flat or a bridge spans too far to print, are left out while one without is found. Overhangs counts the faces overhanging without fins, Bridges those spanning too far, with the longest span in brackets; yellow is critical, red not printable. Rated after the checks were switched on, every way stays listed in its order, shaded by what it finds.</source>
        <translation>Schnelle Finnen hat mehr als eine Möglichkeit gefunden, das Teil aufzustellen. Eine Zeile anklicken, um es so aufzustellen; Teil und Finnen folgen in der 3D-Ansicht. Möglichkeiten, bei denen das Teil in der Luft zu drucken beginnen würde, eine Insel, oder bei denen eine Fläche zu flach liegt oder eine Brücke zu weit spannt, um sie zu drucken, werden weggelassen, solange eine ohne gefunden wird. Überhänge zählt die Flächen, die ohne Finnen überhängen, Brücken die, die zu weit spannen, mit der längsten Spannweite in Klammern; gelb ist kritisch, rot nicht druckbar. Erst nach dem Einschalten der Prüfungen bewertet, bleibt jede Möglichkeit in ihrer Reihenfolge stehen, eingefärbt nach dem, was die Prüfung findet.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="155"/>
        <source>Stand the part another way? The fins are planned anew: fins removed, moved or set to a height of their own, a turn of the part and the counter fin are undone.</source>
        <translation>Das Teil anders aufstellen? Die Finnen werden neu geplant: entfernte, verschobene Finnen und eigene Höhen, eine Drehung des Teils und die Gegenfinne werden aufgehoben.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="100"/>
        <source>No face overhangs without fins.</source>
        <translation>Keine Fläche hängt ohne Finnen über.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="101"/>
        <source>%d island(s): it would start printing in the air there.</source>
        <translation>%d Insel(n): dort würde es in der Luft zu drucken beginnen.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="102"/>
        <source>No islands.</source>
        <translation>Keine Inseln.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="103"/>
        <source>No bridge spans further than %.1f mm.</source>
        <translation>Keine Brücke spannt weiter als %.1f mm.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="174"/>
        <source>Checks whether the part stays standing while it is printed, layer by layer, on its own and held by these fins, which hold it only from their lowest tine up, and shows the plumb line from its centre of mass to the bed. Takes a moment on a large part.</source>
        <translation>Prüft Schicht für Schicht, ob das Teil während des Drucks stehen bleibt, allein und von diesen Finnen gehalten, die es erst ab ihrer untersten Zinke halten, und zeigt das Lot von seinem Schwerpunkt zum Bett. Dauert bei einem großen Teil einen Moment.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="178"/>
        <source>Changed since the stability check: check again.</source>
        <translation>Seit der Prüfung der Standfestigkeit geändert: erneut prüfen.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="180"/>
        <source>The part of this check is gone; delete the check.</source>
        <translation>Das Teil dieser Prüfung gibt es nicht mehr; lösche die Prüfung.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="738"/>
        <source>To remove one fin, click it in the 3D view and press Remove selected fin, or the Delete key. The counter fin goes under the face leaning the other way, or under a face of the part you select. Drag the two arrows on a fin to move it along the face or to change its height, or type the values below; click another fin, or pick it in the list of fins, to put the arrows there. Reset fins undoes every change by hand.</source>
        <translation>Um eine einzelne Finne zu entfernen, klicke sie in der 3D-Ansicht an und drücke „Gewählte Finne entfernen“ oder die Entf-Taste. Die Gegenfinne kommt unter die Fläche, die sich zur anderen Seite neigt, oder unter eine Fläche des Teils, die du wählst. Ziehe an den beiden Pfeilen einer Finne, um sie entlang der Fläche zu verschieben oder ihre Höhe zu ändern, oder tippe die Werte unten ein; klicke eine andere Finne an oder wähle sie in der Liste der Finnen, um die Pfeile dorthin zu setzen. „Finnen zurücksetzen“ nimmt jede Änderung von Hand zurück.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="786"/>
        <source>Save as standard</source>
        <translation>Als Standard speichern</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="787"/>
        <source>New fins start with these values. Fields that differ from the standard are marked, and their button puts the standard back.</source>
        <translation>Neue Finnen starten mit diesen Werten. Felder, die vom Standard abweichen, sind markiert, und ihr Knopf stellt den Standard wieder her.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="791"/>
        <location filename="../taskpanel.py" line="977"/>
        <source>Factory settings</source>
        <translation>Werkseinstellungen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="792"/>
        <source>Forget the saved standard and set every field to the built-in value.</source>
        <translation>Den gespeicherten Standard verwerfen und jedes Feld auf den eingebauten Wert setzen.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="812"/>
        <source>Check stability</source>
        <translation>Standfestigkeit prüfen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="889"/>
        <source>Stand another way</source>
        <translation>Anders aufstellen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="957"/>
        <source>Back to the standard: %s</source>
        <translation>Zurück auf den Standard: %s</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="978"/>
        <source>Forget the saved standard and set every field to the built-in value?</source>
        <translation>Den gespeicherten Standard verwerfen und jedes Feld auf den eingebauten Wert setzen?</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1006"/>
        <location filename="../taskpanel.py" line="1010"/>
        <source>Nothing removed</source>
        <translation>Nichts entfernt</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1017"/>
        <source>Delete the fins?</source>
        <translation>Finnen löschen?</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1018"/>
        <source>These are the last fins. Delete the fins object? A part stood on an edge for these fins alone is laid flat again.</source>
        <translation>Das sind die letzten Finnen. Das Finnen-Objekt löschen? Ein Teil, das nur für diese Finnen auf eine Kante gestellt wurde, wird wieder flach gelegt.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1034"/>
        <source>Delete fins</source>
        <translation>Finnen löschen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1183"/>
        <source>%s %d</source>
        <translation>%s %d</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="446"/>
        <source>Cancel fins</source>
        <translation>Finnen abbrechen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="76"/>
        <source>Click a fin of these fins in the 3D view first.</source>
        <translation>Klicke zuerst eine dieser Finnen in der 3D-Ansicht an.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="81"/>
        <source>Distance of the middle of the fin from the left end of the face, seen from outside. Type a value to move the fin there.</source>
        <translation>Abstand der Mitte der Finne vom linken Ende der Fläche, von außen gesehen. Wert eingeben, um die Finne dorthin zu verschieben.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="86"/>
        <source>Position of the fin around the cylinder or tube, measured at the middle of its tines, in degrees from 0°, where it is first placed. Type a value to turn the part to it; the fin keeps its place.</source>
        <translation>Position der Finne am Umfang des Zylinders oder Rohrs, gemessen an der Mitte der Zinken, in Grad ab 0°, wo sie zuerst gesetzt wird. Wert eingeben, um das Teil dorthin zu drehen; die Finne bleibt an ihrem Platz.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="91"/>
        <source>Height of this fin alone. Type a value to set it; Reset fins gives it the height of the others again.</source>
        <translation>Höhe nur dieser Finne. Wert eingeben, um sie zu setzen; Finnen zurücksetzen gibt ihr wieder die Höhe der anderen.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="130"/>
        <source>Stand</source>
        <translation>Aufstellung</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="135"/>
        <source>Stands on</source>
        <translation>Steht auf</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="135"/>
        <source>Length</source>
        <translation>Länge</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="133"/>
        <source>Islands</source>
        <translation>Inseln</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="137"/>
        <source>Fins under</source>
        <translation>Finnen unter</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="137"/>
        <source>Area</source>
        <translation>Flächeninhalt</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="165"/>
        <source>Tips at layer %d, %.1f mm high</source>
        <translation>Kippt bei Schicht %d, %.1f mm hoch</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="96"/>
        <source>%d faces overhang flatter than %.0f degrees from the bed without fins.</source>
        <translation>%d Flächen hängen flacher als %.0f Grad zur Bettebene über, ohne Finnen.</translation>
    </message>
    <message>
        <location filename="../analysis.py" line="98"/>
        <source>%d faces overhang flatter than %.0f degrees from the bed without fins, too flat to print.</source>
        <translation>%d Flächen hängen flacher als %.0f Grad zur Bettebene über, ohne Finnen, zu flach zum Drucken.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="748"/>
        <source>Reset fins</source>
        <translation>Finnen zurücksetzen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1053"/>
        <location filename="../taskpanel.py" line="1057"/>
        <source>No counter fin</source>
        <translation>Keine Gegenfinne</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1387"/>
        <source>no tine of the fin finds the face there</source>
        <translation>dort trifft keine Zinke der Finne die Fläche</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1731"/>
        <source>Not possible</source>
        <translation>Nicht möglich</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1777"/>
        <source>Notes</source>
        <translation>Hinweise</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1770"/>
        <source>%d fin(s), %.2f mm high, %.2f mm thick</source>
        <translation>%d Finne(n), %.2f mm hoch, %.2f mm dick</translation>
    </message>
    <message>
        <location filename="../export_3mf.py" line="74"/>
        <source>surface deviation and angular deviation must be greater than 0</source>
        <translation>Oberflächenabweichung und Winkelabweichung müssen größer als 0 sein</translation>
    </message>
    <message>
        <location filename="../export_3mf.py" line="76"/>
        <location filename="../export_step.py" line="38"/>
        <source>nothing to export</source>
        <translation>nichts zu exportieren</translation>
    </message>
    <message>
        <location filename="../export_3mf.py" line="79"/>
        <location filename="../export_step.py" line="41"/>
        <source>%s has no solid to export</source>
        <translation>%s hat keinen Volumenkörper zum Exportieren</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="482"/>
        <source>the selected face is not planar</source>
        <translation>die gewählte Fläche ist nicht eben</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="405"/>
        <source>the selected face curves inward; fins go under the outside of a cylinder or tube</source>
        <translation>die gewählte Fläche wölbt sich nach innen; Finnen kommen unter die Außenseite eines Zylinders oder Rohrs</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="151"/>
        <source>the round side lies horizontal at its lowest line; it rests on the bed or needs regular support</source>
        <translation>die runde Seite liegt an ihrer untersten Linie waagerecht; sie liegt auf dem Bett oder braucht normale Stützen</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="156"/>
        <source>the selected curved face does not reach round to its lowest line, under which its fin would stand</source>
        <translation>die gewählte gewölbte Fläche reicht nicht bis zu ihrer untersten Linie, unter der ihre Finne stünde</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="411"/>
        <source>the lowest line of the selected face is cut away</source>
        <translation>die unterste Linie der gewählten Fläche ist weggeschnitten</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="506"/>
        <source>fin_height %.2f reaches above the face (%.2f)</source>
        <translation>Finnenhöhe %.2f reicht über die Fläche hinaus (%.2f)</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="527"/>
        <source>no tine fits below %.2f mm</source>
        <translation>unter %.2f mm passt keine Zinke</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="529"/>
        <source>only %d of %d tines fit below %.2f mm</source>
        <translation>nur %d von %d Zinken passen unter %.2f mm</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="638"/>
        <source>the face is narrower than the %.2f mm a fin needs at every tine</source>
        <translation>die Fläche ist an jeder Zinke schmaler als die %.2f mm, die eine Finne braucht</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="666"/>
        <source>the face is too short for a fin on each corner</source>
        <translation>die Fläche ist zu kurz für eine Finne auf jeder Ecke</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="672"/>
        <source>the face is too short for a fin of %.2f mm</source>
        <translation>die Fläche ist zu kurz für eine Finne von %.2f mm</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="690"/>
        <source>%d fins do not fit side by side on this face</source>
        <translation>%d Finnen passen nicht nebeneinander unter diese Fläche</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="986"/>
        <source>the fins overlap the part by %.4f mm³</source>
        <translation>die Finnen überschneiden das Teil um %.4f mm³</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1021"/>
        <source>fins under the selected face alone, not reaching over the groove: %s</source>
        <translation>Finnen nur unter der gewählten Fläche, nicht über die Rille hinweg: %s</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1045"/>
        <location filename="../params.py" line="126"/>
        <source>tines (%.2f mm) are wider than the fin (%.2f mm)</source>
        <translation>die Zinken (%.2f mm) sind breiter als die Finne (%.2f mm)</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1084"/>
        <source>fin %d would pass fin %d; a fin stays between its neighbours</source>
        <translation>die Finne %d käme an der Finne %d vorbei; eine Finne bleibt zwischen ihren Nachbarinnen</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1087"/>
        <source>fins %d and %d stand %.2f mm apart, closer than %.2f mm</source>
        <translation>die Finnen %d und %d stehen %.2f mm auseinander, näher als %.2f mm</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1128"/>
        <source>fin %d is %.2f mm high, above the face (%.2f mm)</source>
        <translation>die Finne %d ist %.2f mm hoch, höher als die Fläche (%.2f mm)</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1132"/>
        <source>fin %d is lower than its first tine</source>
        <translation>die Finne %d ist niedriger als ihre erste Zinke</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1090"/>
        <source>every fin is removed; delete the fins instead, or bring them back</source>
        <translation>alle Finnen sind entfernt; lösche stattdessen die Finnen oder hole sie zurück</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="147"/>
        <source>the selected face does not overhang; it faces up or sideways</source>
        <translation>die gewählte Fläche hängt nicht über; sie zeigt nach oben oder zur Seite</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="148"/>
        <source>the selected face is horizontal; it rests on the bed or needs regular support</source>
        <translation>die gewählte Fläche liegt waagerecht; sie liegt auf dem Bett oder braucht normale Stützen</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1226"/>
        <source>fins moved along the face to where their tines rest, beside a hole or recess under their planned place: %s</source>
        <translation>Finnen entlang der Fläche dorthin gerückt, wo ihre Zinken aufliegen, neben ein Loch oder eine Vertiefung unter ihrem geplanten Platz: %s</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1228"/>
        <source>fin %d by %.2f mm</source>
        <translation>Finne %d um %.2f mm</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1235"/>
        <source>tines at %s mm above the bed left out: the face is narrower there than the fin</source>
        <translation>Zinken bei %s mm über dem Bett weggelassen: die Fläche ist dort schmaler als die Finne</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1240"/>
        <source>the face is inclined %.0f degrees to the bed, outside %.0f to %.0f</source>
        <translation>die Fläche ist %.0f Grad zur Bettebene geneigt, außerhalb von %.0f bis %.0f</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1245"/>
        <source>tines are %.2f mm long, shorter than %.2f bead widths; the slicer may not print them to the face</source>
        <translation>die Zinken sind %.2f mm lang, kürzer als %.2f Raupenbreiten; der Slicer druckt sie womöglich nicht bis an die Fläche</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1249"/>
        <source>the part stands on one point of its rim: a chamfer on the rim and a brim in the slicer give it more hold on the bed</source>
        <translation>das Teil steht auf einem Punkt seines Rands: eine Fase am Rand und ein Brim im Slicer geben ihm mehr Halt auf dem Bett</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="145"/>
        <source>no face of the part leans over the bed and takes fins</source>
        <translation>keine Fläche des Teils hängt über und nimmt Finnen auf</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="153"/>
        <source>the part cannot stand so that this face takes fins</source>
        <translation>das Teil lässt sich nicht so aufstellen, dass diese Fläche Finnen aufnimmt</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1505"/>
        <source>Select an edge or a face, a face and the edge or the chamfer or fillet it is to stand on, or the two faces beside a fillet.</source>
        <translation>Wähle eine Kante oder eine Fläche, eine Fläche und die Kante oder die Fase oder Verrundung, auf der sie stehen soll, oder die beiden Flächen neben einer Verrundung.</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1556"/>
        <source>the fins do not fit under the selected face standing this way: %s</source>
        <translation>die Finnen passen in dieser Lage nicht unter die gewählte Fläche: %s</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1164"/>
        <source>no tine finds the face; it has a recess or hole at every tine</source>
        <translation>keine Zinke trifft die Fläche; sie hat an jeder Zinke eine Aussparung oder ein Loch</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="991"/>
        <source>a fin comes within %.3f mm of the part, closer than the %.3f mm it keeps from the face</source>
        <translation>eine Finne kommt dem Teil bis auf %.3f mm nahe, näher als die %.3f mm, die sie von der Fläche hält</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1222"/>
        <source>tines at %s mm above the bed left out: a recess or hole in the face lies under them</source>
        <translation>Zinken bei %s mm über dem Bett weggelassen: unter ihnen liegt eine Aussparung oder ein Loch in der Fläche</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1231"/>
        <source>fins at %s mm from the end of the face left out: none of their tines lies wholly on the face</source>
        <translation>Finnen bei %s mm vom Ende der Fläche weggelassen: keine ihrer Zinken liegt ganz auf der Fläche</translation>
    </message>
    <message>
        <location filename="../mesh_input.py" line="26"/>
        <source>the mesh is empty</source>
        <translation>das Netz ist leer</translation>
    </message>
    <message>
        <location filename="../mesh_input.py" line="32"/>
        <location filename="../mesh_input.py" line="34"/>
        <source>the mesh is not closed</source>
        <translation>das Netz ist nicht geschlossen</translation>
    </message>
    <message>
        <location filename="../orient.py" line="360"/>
        <source>the tilt angle must lie between 0 and 90 degrees</source>
        <translation>der Neigungswinkel muss zwischen 0 und 90 Grad liegen</translation>
    </message>
    <message>
        <location filename="../orient.py" line="366"/>
        <source>the edge is curved; select a straight edge</source>
        <translation>die Kante ist gekrümmt; wähle eine gerade Kante</translation>
    </message>
    <message>
        <location filename="../orient.py" line="368"/>
        <source>the edge is not horizontal</source>
        <translation>die Kante liegt nicht waagerecht</translation>
    </message>
    <message>
        <location filename="../orient.py" line="370"/>
        <location filename="../orient.py" line="485"/>
        <source>the edge does not lie on the bed</source>
        <translation>die Kante liegt nicht auf dem Bett; wähle zusätzlich die Fläche, die auf das Bett soll</translation>
    </message>
    <message>
        <location filename="../orient.py" line="380"/>
        <source>the part cannot stand on this edge</source>
        <translation>das Teil kann nicht auf dieser Kante stehen</translation>
    </message>
    <message>
        <location filename="../orient.py" line="398"/>
        <source>the part cannot rest on this face</source>
        <translation>das Teil kann nicht auf dieser Fläche liegen, andere Teile davon reichen tiefer</translation>
    </message>
    <message>
        <location filename="../orient.py" line="422"/>
        <source>the rim has no flat face to stand on</source>
        <translation>der Rand hat keine ebene Fläche, auf der das Teil stehen kann</translation>
    </message>
    <message>
        <location filename="../orient.py" line="446"/>
        <source>the two faces point in opposite directions</source>
        <translation>die beiden Flächen zeigen in entgegengesetzte Richtungen</translation>
    </message>
    <message>
        <location filename="../orient.py" line="464"/>
        <source>the part cannot rest between these faces</source>
        <translation>das Teil kann nicht zwischen diesen Flächen aufliegen, andere Teile davon reichen tiefer</translation>
    </message>
    <message>
        <location filename="../orient.py" line="487"/>
        <source>an edge alone stands the part only at 45 degrees; for another angle select the face that is to lie on the bed</source>
        <translation>eine Kante allein stellt das Teil nur bei 45 Grad auf; für einen anderen Winkel wähle zusätzlich die Fläche, die auf das Bett soll</translation>
    </message>
    <message>
        <location filename="../orient.py" line="475"/>
        <source>the edge is not an edge of the selected face</source>
        <translation>die Kante gehört nicht zur gewählten Fläche</translation>
    </message>
    <message>
        <location filename="../orient.py" line="491"/>
        <source>a rounded face does not lie on the bed with its edge; select it alone, or the two faces beside it</source>
        <translation>eine gewölbte Fläche liegt nicht mit ihrer Kante auf dem Bett; wähle sie allein oder die beiden Flächen daneben</translation>
    </message>
    <message>
        <location filename="../limits.py" line="110"/>
        <location filename="../params.py" line="84"/>
        <source>%s is not a finite number</source>
        <translation>%s ist keine endliche Zahl</translation>
    </message>
    <message>
        <location filename="../limits.py" line="113"/>
        <source>%s must lie between %.0f and %.0f degrees</source>
        <translation>%s muss zwischen %.0f und %.0f Grad liegen</translation>
    </message>
    <message>
        <location filename="../limits.py" line="116"/>
        <source>overhang_unprintable must not be steeper than overhang_critical</source>
        <translation>„Nicht druckbar unter“ darf bei Überhängen nicht steiler sein als „Kritisch unter“</translation>
    </message>
    <message>
        <location filename="../limits.py" line="120"/>
        <source>%s must be 0 or greater</source>
        <translation>%s muss 0 oder größer sein</translation>
    </message>
    <message>
        <location filename="../limits.py" line="122"/>
        <source>bridge_unprintable must not be shorter than bridge_critical</source>
        <translation>„Nicht druckbar über“ darf bei Brücken nicht kürzer sein als „Kritisch über“</translation>
    </message>
    <message>
        <location filename="../params.py" line="91"/>
        <source>%s must be greater than 0</source>
        <translation>%s muss größer als 0 sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="97"/>
        <source>%s must be 0 (automatic) or greater</source>
        <translation>%s muss 0 (automatisch) oder größer sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="100"/>
        <source>tine_clearance must be 0 (touching) or greater</source>
        <translation>der Abstand Zinke zum Teil muss 0 (berührend) oder größer sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="102"/>
        <source>foot_overhang must be 0 or greater</source>
        <translation>Fußüberstand muss 0 oder größer sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="104"/>
        <source>brim_width must be 0 (no brim) or greater</source>
        <translation>die Brim-Breite muss 0 (kein Brim) oder größer sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="106"/>
        <source>bead_width is less than half the nozzle diameter</source>
        <translation>die Raupenbreite ist kleiner als der halbe Düsendurchmesser</translation>
    </message>
    <message>
        <location filename="../params.py" line="108"/>
        <source>layer_height is greater than the nozzle diameter</source>
        <translation>die Schichthöhe ist größer als der Düsendurchmesser</translation>
    </message>
    <message>
        <location filename="../params.py" line="110"/>
        <source>tine_layers must be at least 1</source>
        <translation>die Zinkenhöhe in Schichten muss mindestens 1 sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="112"/>
        <source>tine_width_beads must be at least 1</source>
        <translation>Zinkenbreite in Raupen muss mindestens 1 sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="114"/>
        <source>tine_spacing %.2f mm leaves no free layer between the tines; it needs at least %.2f mm</source>
        <translation>Zinkenabstand %.2f mm lässt keine freie Schicht zwischen den Zinken; nötig sind mindestens %.2f mm</translation>
    </message>
    <message>
        <location filename="../params.py" line="121"/>
        <source>%s must be one of %s</source>
        <translation>%s muss eines von %s sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="124"/>
        <source>fin_count must be at least 1</source>
        <translation>Anzahl Finnen muss mindestens 1 sein</translation>
    </message>
    <message>
        <location filename="../shapes.py" line="87"/>
        <source>%s has no shape</source>
        <translation>%s hat keine Form</translation>
    </message>
    <message>
        <location filename="../handles.py" line="535"/>
        <source>No 3D view of %s is open to edit the fins in.</source>
        <translation>Von %s ist keine 3D-Ansicht offen, in der die Finnen bearbeitet werden können.</translation>
    </message>
    <message>
        <location filename="../check.py" line="35"/>
        <source>Stability check of %s</source>
        <translation>Standfestigkeit von %s</translation>
    </message>
    <message>
        <location filename="../check.py" line="36"/>
        <source>Part check of %s</source>
        <translation>Prüfung von %s</translation>
    </message>
    <message>
        <location filename="../check.py" line="37"/>
        <source>Bridge check of %s</source>
        <translation>Brückenprüfung von %s</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="39"/>
        <source>Check limits</source>
        <translation>Prüfgrenzen</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="48"/>
        <location filename="../taskpanel.py" line="133"/>
        <source>Overhangs</source>
        <translation>Überhänge</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="49"/>
        <source>Critical below</source>
        <translation>Kritisch unter</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="55"/>
        <source>Not printable below</source>
        <translation>Nicht druckbar unter</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="56"/>
        <source>Faces lying flatter than this from the bed, without fins, are too flat to print and marked red. At most the critical limit.</source>
        <translation>Flächen ohne Finnen, die flacher als dieser Winkel zur Bettebene liegen, sind zu flach zum Drucken und werden rot markiert. Höchstens so groß wie die kritische Grenze.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="59"/>
        <source>Least area</source>
        <translation>Mindestfläche</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="50"/>
        <source>Faces lying flatter than this from the bed, without fins, are critical and marked yellow. 0 degrees is a face lying flat over the bed, 90 a vertical wall, as PrusaSlicer measures its overhang threshold; Cura measures from the vertical, its value is 90 degrees minus this one.</source>
        <translation>Flächen ohne Finnen, die flacher als dieser Winkel zur Bettebene liegen, sind kritisch und werden gelb markiert. 0 Grad ist eine Fläche, die flach über dem Bett liegt, 90 Grad eine senkrechte Wand, so wie PrusaSlicer seine Überhangschwelle misst; Cura misst von der Senkrechten aus, sein Wert ist 90 Grad minus diesem.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="60"/>
        <source>Overhanging faces smaller than this, like the corner facets of a chamfer, are printed over by the slicer without trouble and not reported.</source>
        <translation>Überhängende Flächen, die kleiner sind, etwa die Eckflächen einer Fase, druckt der Slicer ohne Weiteres; sie werden nicht gemeldet.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="64"/>
        <location filename="../taskpanel.py" line="134"/>
        <source>Bridges</source>
        <translation>Brücken</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="65"/>
        <source>Critical over</source>
        <translation>Kritisch über</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="66"/>
        <source>A bridge, a face resting on the layer below at two or more sides, spanning further than this between its supports, is critical and marked yellow.</source>
        <translation>Eine Brücke, eine Fläche, die an zwei oder mehr Seiten auf der Schicht darunter aufliegt, ist kritisch und wird gelb markiert, wenn sie weiter als dieser Wert zwischen ihren Auflagen spannt.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="70"/>
        <source>Not printable over</source>
        <translation>Nicht druckbar über</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="71"/>
        <source>A bridge spanning further than this sags too far to print and is marked red. At least the critical span.</source>
        <translation>Eine Brücke, die weiter spannt, hängt zu stark durch, um sie zu drucken, und wird rot markiert. Mindestens so groß wie die kritische Spannweite.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="75"/>
        <source>Stability</source>
        <translation>Standfestigkeit</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="76"/>
        <source>At risk of tipping below</source>
        <translation>Kippgefährdet unter</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="77"/>
        <source>The tipping angle: how far the part would have to lean before the plumb line from its centre of mass left the footprint. A tall part needs a wider tipping margin than a flat one for the same angle. Below this, the part is at risk of tipping and shown yellow; below 0 it tips, shown red. Check stability says which acceleration from the side it withstands.</source>
        <translation>Der Kippwinkel: wie weit sich das Teil neigen müsste, bis das Lot von seinem Schwerpunkt die Standfläche verlässt. Ein hohes Teil braucht für denselben Winkel einen größeren Kippabstand als ein flaches. Darunter ist das Teil kippgefährdet und wird gelb gezeigt; unter 0 kippt es, rot gezeigt. Standfestigkeit prüfen sagt, welche Beschleunigung von der Seite es aushält.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="90"/>
        <source>How strictly the checks rate a part. Normal, built in, allows for what common printers manage and for the grip of the first layer on the bed. Strict counts the geometry alone: what would need support is not printable, and the part needs a larger tipping angle. Custom: the limits set below by hand.</source>
        <translation>Wie streng die Prüfungen ein Teil bewerten. Normal, eingebaut, rechnet mit dem, was gängige Drucker schaffen, und mit der Haftung der ersten Schicht auf dem Bett. Streng zählt nur die Geometrie: was eine Stütze bräuchte, ist nicht druckbar, und das Teil braucht einen größeren Kippwinkel. Eigene: die unten von Hand gesetzten Grenzen.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="86"/>
        <source>Strictness</source>
        <translation>Strenge</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="87"/>
        <source>Strict</source>
        <translation>Streng</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="88"/>
        <source>Normal</source>
        <translation>Normal</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="89"/>
        <source>Custom</source>
        <translation>Eigene</translation>
    </message>
</context>
<context>
    <name>FinSnap_AddCounterFin</name>
    <message>
        <location filename="../commands.py" line="797"/>
        <source>Add counter fin</source>
        <translation>Gegenfinne hinzufügen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="798"/>
        <source>Adds a fin on the opposite side of existing fins, against tipping away, as large as the main fin; fewer counter tines in the panel make it smaller. Select the fins: the face leaning the other way is found automatically. Or select a face of the part as well to choose it yourself. To remove the counter fin, clear its face in the property view.</source>
        <translation>Fügt vorhandenen Finnen eine Finne auf der Gegenseite hinzu, gegen Wegkippen, so groß wie die Hauptfinne; weniger Zinken der Gegenfinne im Aufgabenfenster machen sie kleiner. Die Finnen auswählen: Die zur anderen Seite geneigte Fläche wird automatisch gefunden. Oder zusätzlich eine Fläche des Teils auswählen, um sie selbst festzulegen. Zum Entfernen die Fläche der Gegenfinne in der Eigenschaftenansicht leeren.</translation>
    </message>
</context>
<context>
    <name>FinSnap_AddFins</name>
    <message>
        <location filename="../commands.py" line="765"/>
        <source>Add fins</source>
        <translation>Finnen hinzufügen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="766"/>
        <source>Select the face that leans over the bed; optionally a second face on the opposite side for a counter fin</source>
        <translation>Die Fläche auswählen, die überhängt; optional eine zweite Fläche auf der Gegenseite für eine Gegenfinne</translation>
    </message>
</context>
<context>
    <name>FinSnap_CheckBridges</name>
    <message>
        <location filename="../commands.py" line="1089"/>
        <source>Check bridges</source>
        <translation>Brücken prüfen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="1090"/>
        <source>Checks the selected part, as it stands, for bridges: faces that span a gap between supports on the layer below, at two or more sides, which the slicer prints as straight lines across. Says how far each spans, rated by the check limits, and keeps it as a bridge check in the tree, which shows where they span too far on the underside of the part. Once the part, its place or its fins change, the check is marked out of date; double-click it to check again.</source>
        <translation>Prüft das ausgewählte Teil, so wie es steht, auf Brücken: Flächen, die eine Lücke zwischen Auflagen auf der Schicht darunter überspannen, an zwei oder mehr Seiten, die der Slicer als gerade Linien quer hinüber druckt. Sagt, wie weit jede spannt, bewertet nach den Prüfgrenzen, und legt es als Brückenprüfung im Baum ab, die an der Unterseite des Teils zeigt, wo sie zu weit spannen. Ändern sich das Teil, seine Lage oder seine Finnen, wird die Prüfung als veraltet markiert; zum erneuten Prüfen doppelklicken.</translation>
    </message>
</context>
<context>
    <name>FinSnap_CheckLimits</name>
    <message>
        <location filename="../commands.py" line="1189"/>
        <source>Check limits...</source>
        <translation>Prüfgrenzen...</translation>
    </message>
    <message>
        <location filename="../commands.py" line="1190"/>
        <source>Opens the limits the checks rate by, in Edit &gt; Preferences: the strictness, strict or normal, or limits of your own for overhangs, bridges and the tipping margin.</source>
        <translation>Öffnet die Grenzen, nach denen die Prüfungen bewerten, unter Bearbeiten &gt; Einstellungen: die Strenge, streng oder normal, oder eigene Grenzen für Überhänge, Brücken und den Kippabstand.</translation>
    </message>
</context>
<context>
    <name>FinSnap_CheckPart</name>
    <message>
        <location filename="../commands.py" line="1113"/>
        <source>Check part</source>
        <translation>Teil prüfen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="1114"/>
        <source>Checks the selected part, with or without fins, as it stands, for everything that keeps it from printing, all at once: faces overhanging without fins, bridges spanning too far, islands, where it would start printing in the air, and whether it stays standing while it is printed. Says what it found and keeps it as a part check in the tree, which shows it all: the eye shows or hides it, deleting the check removes it. Once the part, its place or its fins change, the check is marked out of date; double-click it to check again.</source>
        <translation>Prüft das ausgewählte Teil, mit oder ohne Finnen, so wie es steht, auf einmal auf alles, was den Druck verhindert: Flächen, die ohne Finnen überhängen, zu weit gespannte Brücken, Inseln, wo es in der Luft zu drucken beginnen würde, und ob es während des Drucks stehen bleibt. Sagt, was gefunden wurde, und legt es als Prüfung im Baum ab, die alles anzeigt: das Auge blendet es ein und aus, Löschen der Prüfung entfernt es. Ändern sich das Teil, seine Lage oder seine Finnen, wird die Prüfung als veraltet markiert; zum erneuten Prüfen doppelklicken.</translation>
    </message>
</context>
<context>
    <name>FinSnap_CheckStability</name>
    <message>
        <location filename="../commands.py" line="1036"/>
        <source>Check stability</source>
        <translation>Standfestigkeit prüfen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="1037"/>
        <source>Checks whether the selected part stays standing while it is printed, layer by layer, as it grows and its centre of mass moves: first on its own, then, where it would tip over, held by its fins, which hold it only from their lowest tine up. Says at which layer it would tip and which way. Keeps it as a stability check in the tree, which shows the part coloured by height, the layer it tips at and the plumb line from its centre of mass to the bed: the eye shows or hides them, deleting the check removes them. Once the part, its place or its fins change, the check is marked out of date; double-click it to check again.</source>
        <translation>Prüft Schicht für Schicht, ob das ausgewählte Teil während des Drucks stehen bleibt, während es wächst und sein Schwerpunkt wandert: zuerst allein, dann, wo es umkippen würde, von seinen Finnen gehalten, die es erst ab ihrer untersten Zinke halten. Sagt, bei welcher Schicht es kippen würde und wohin. Legt es als Standfestigkeitsprüfung im Baum ab, die das Teil nach Höhe eingefärbt, die Schicht, an der es kippt, und das Lot von seinem Schwerpunkt zum Bett zeigt: das Auge blendet sie ein und aus, Löschen der Prüfung entfernt sie. Ändern sich das Teil, seine Lage oder seine Finnen, wird die Prüfung als veraltet markiert; zum erneuten Prüfen doppelklicken.</translation>
    </message>
</context>
<context>
    <name>FinSnap_Export3MF</name>
    <message>
        <location filename="../commands.py" line="947"/>
        <source>Export 3MF</source>
        <translation>3MF exportieren</translation>
    </message>
    <message>
        <location filename="../commands.py" line="948"/>
        <source>Export the selection to 3MF, every body as its own object for the slicer. With nothing selected, all fins of the document are exported together with their parts.</source>
        <translation>Die Auswahl als 3MF exportieren, jeden Körper als eigenes Objekt für den Slicer. Ist nichts ausgewählt, werden alle Finnen des Dokuments mit ihren Teilen exportiert.</translation>
    </message>
</context>
<context>
    <name>FinSnap_ExportSTEP</name>
    <message>
        <location filename="../commands.py" line="971"/>
        <source>Export STEP</source>
        <translation>STEP exportieren</translation>
    </message>
    <message>
        <location filename="../commands.py" line="972"/>
        <source>Export the selection to STEP, with exact surfaces instead of a mesh. The slicer loads it as one object with a part per body: split it into objects there, so part and fins are printed separately. With nothing selected, all fins of the document are exported together with their parts.</source>
        <translation>Die Auswahl als STEP exportieren, mit exakten Flächen statt eines Netzes. Der Slicer lädt sie als ein Objekt mit einem Teil je Körper: dort in Objekte trennen, damit Bauteil und Finnen getrennt gedruckt werden. Ist nichts ausgewählt, werden alle Finnen des Dokuments mit ihren Bauteilen exportiert.</translation>
    </message>
</context>
<context>
    <name>FinSnap_IslandsWhileEditing</name>
    <message>
        <location filename="../commands.py" line="1139"/>
        <source>Islands and bridges while editing</source>
        <translation>Inseln und Brücken beim Bearbeiten</translation>
    </message>
    <message>
        <location filename="../commands.py" line="1140"/>
        <source>While on, fins check their part for islands and bridges as they are made and edited, and Quick fins rates the ways to stand it by them. Off, they are not checked then, which keeps a large part quick on a slow computer: bridge faces count as overhangs meanwhile, and Check part checks them at the end.</source>
        <translation>Eingeschaltet prüfen Finnen ihr Teil beim Erzeugen und Bearbeiten auf Inseln und Brücken, und Schnelle Finnen bewertet danach die Möglichkeiten, es aufzustellen. Ausgeschaltet wird dabei nicht geprüft, das hält ein großes Teil auf einem langsamen Rechner schnell: Brückenflächen zählen solange als Überhänge, und die Teilprüfung prüft sie am Ende.</translation>
    </message>
</context>
<context>
    <name>FinSnap_LayFlat</name>
    <message>
        <location filename="../commands.py" line="447"/>
        <source>Lay flat again</source>
        <translation>Wieder flach legen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="448"/>
        <source>Puts a part stood on an edge back as it lay before. Select the part or its fins. If the part has fins, it asks whether to delete them; kept fins move along with the part and are rebuilt once it is moved again. Deleting the last fins of a part lays it flat as well.</source>
        <translation>Legt ein auf eine Kante gestelltes Teil wieder so hin, wie es vorher lag. Wähle das Teil oder seine Finnen. Hat das Teil Finnen, wird gefragt, ob sie gelöscht werden; behaltene Finnen bewegen sich mit dem Teil und werden neu gebaut, sobald es wieder bewegt wird. Das Löschen der letzten Finnen eines Teils legt es ebenfalls flach.</translation>
    </message>
</context>
<context>
    <name>FinSnap_MeshToSolid</name>
    <message>
        <location filename="../commands.py" line="843"/>
        <source>Mesh to solid</source>
        <translation>Netz zu Volumenkörper</translation>
    </message>
    <message>
        <location filename="../commands.py" line="844"/>
        <source>Turn a selected STL mesh into a solid with planar faces, so fins can be added</source>
        <translation>Ein ausgewähltes STL-Netz in einen Volumenkörper mit ebenen Flächen umwandeln, damit Finnen hinzugefügt werden können</translation>
    </message>
</context>
<context>
    <name>FinSnap_QuickFins</name>
    <message>
        <location filename="../commands.py" line="524"/>
        <source>Quick fins</source>
        <translation>Schnelle Finnen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="525"/>
        <source>Stands the part up and adds one fin in the middle of a face in one step, then opens the panel to adjust it. Select the edge the part is to stand on: the fins go under the largest face that leans over the bed. Or select the face the fins are to support: the part is turned so that it leans 45 degrees over the bed, on its longest edge; select one of its edges as well to stand on that one, or, after the face, a chamfer or fillet to rest on. A chamfer or fillet alone, or the two faces beside a fillet, carry the part as well. The rim or the curved side of a cylinder or tube stands it on its rim, with one fin under its lowest line. A counter fin, where wanted, is added in the panel. Where the part can stand on another edge, or the fins can go under another face, a table at the top of the panel lists them to choose from; ways where the part would start printing in the air are left out while one without is found.</source>
        <translation>Stellt das Teil auf und setzt in einem Schritt eine Finne in die Mitte einer Fläche, dann öffnet sich das Aufgabenfenster zum Anpassen. Wähle die Kante, auf der das Teil stehen soll: Die Finnen kommen unter die größte Fläche, die überhängt. Oder wähle die Fläche, die gestützt werden soll: Das Teil wird so gedreht, dass sie mit 45 Grad über dem Bett hängt, auf ihrer längsten Kante; wähle zusätzlich eine ihrer Kanten, um auf dieser zu stehen, oder nach der Fläche eine Fase oder Verrundung, auf der das Teil liegen soll. Eine Fase oder Verrundung allein oder die beiden Flächen neben einer Verrundung tragen das Teil ebenfalls. Der Rand oder die gewölbte Seite eines Zylinders oder Rohrs stellt es auf seinen Rand, mit einer Finne unter seiner untersten Linie. Eine Gegenfinne fügst du bei Bedarf im Aufgabenfenster hinzu. Kann das Teil auch auf einer anderen Kante stehen oder passen die Finnen auch unter eine andere Fläche, listet eine Tabelle oben im Aufgabenfenster diese Möglichkeiten zur Auswahl auf; Möglichkeiten, bei denen das Teil in der Luft zu drucken beginnen würde, werden weggelassen, solange es eine ohne gibt.</translation>
    </message>
</context>
<context>
    <name>FinSnap_Tilt</name>
    <message>
        <location filename="../commands.py" line="317"/>
        <source>Stand on edge</source>
        <translation>Auf Kante stellen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="318"/>
        <source>Select an edge of the part and the face of that edge that is to lie on the bed. The face is laid onto the bed, the part is turned about the edge by the tilt angle and set back onto the bed, standing on the edge. For an edge already on the bed, the edge alone is enough; so it is for an edge between two flat faces at a right angle, on which the part stands at 45 degrees. A face alone, a chamfer or a fillet, is laid onto the bed and carries the part: a chamfer lies flat on it, a fillet touches it along its middle. Two faces alone, such as the two beside a fillet, stand the part on what joins them, both equally steep. The rim of a cylinder or tube stands it on that rim, leaning to the front.</source>
        <translation>Wähle eine Kante des Teils und die Fläche dieser Kante, die auf dem Bett liegen soll. Die Fläche wird auf das Bett gelegt, das Teil um den Neigungswinkel um die Kante gedreht und wieder auf das Bett gesetzt, sodass es auf der Kante steht. Liegt die Kante schon auf dem Bett, genügt die Kante allein; ebenso bei einer Kante zwischen zwei ebenen Flächen im rechten Winkel, auf der das Teil dann mit 45 Grad steht. Eine Fläche allein, eine Fase oder eine Verrundung, wird auf das Bett gelegt und trägt das Teil: eine Fase liegt flach auf, eine Verrundung berührt das Bett entlang ihrer Mitte. Zwei Flächen allein, etwa die beiden neben einer Verrundung, stellen das Teil auf das, was sie verbindet, beide gleich steil. Der Rand eines Zylinders oder Rohrs stellt es auf diesen Rand, nach vorn geneigt.</translation>
    </message>
</context>
<context>
    <name>Workbench</name>
    <message>
        <location filename="../init_gui.py" line="20"/>
        <source>FinSnap</source>
        <translation>FinSnap</translation>
    </message>
    <message>
        <location filename="../init_gui.py" line="21"/>
        <source>Breakaway fins for parts printed standing on an edge</source>
        <translation>Abbrechbare Finnen für Teile, die auf einer Kante stehend gedruckt werden</translation>
    </message>
</context>
</TS>
