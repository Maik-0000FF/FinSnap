<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="de" sourcelanguage="en">
<context>
    <name>App::Property</name>
    <message>
        <location filename="../feature.py" line="129"/>
        <source>Slicer</source>
        <translation>Slicer</translation>
    </message>
    <message>
        <location filename="../feature.py" line="130"/>
        <source>Connection</source>
        <translation>Verbindung</translation>
    </message>
    <message>
        <location filename="../feature.py" line="131"/>
        <source>Tines</source>
        <translation>Zinken</translation>
    </message>
    <message>
        <location filename="../feature.py" line="132"/>
        <source>Fin</source>
        <translation>Finne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="133"/>
        <source>Placement of fins</source>
        <translation>Lage der Finnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="134"/>
        <source>Foot</source>
        <translation>Fuß</translation>
    </message>
    <message>
        <location filename="../feature.py" line="135"/>
        <source>Counter fin</source>
        <translation>Gegenfinne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="136"/>
        <source>Source</source>
        <translation>Quelle</translation>
    </message>
    <message>
        <location filename="../feature.py" line="137"/>
        <source>Result</source>
        <translation>Ergebnis</translation>
    </message>
    <message>
        <location filename="../feature.py" line="222"/>
        <source>Nozzle diameter of the print profile</source>
        <translation>Düsendurchmesser im Druckprofil</translation>
    </message>
    <message>
        <location filename="../feature.py" line="226"/>
        <source>Extrusion width of the outer perimeter</source>
        <translation>Extrusionsbreite der Außenwand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="230"/>
        <source>Layer height of the print profile</source>
        <translation>Schichthöhe im Druckprofil</translation>
    </message>
    <message>
        <location filename="../feature.py" line="234"/>
        <source>Height of the first layer</source>
        <translation>Höhe der ersten Schicht</translation>
    </message>
    <message>
        <location filename="../feature.py" line="238"/>
        <source>Width of the brim the slicer prints round the part and the fins on the bed, 0 without. Check stability counts it as standing on the bed with them.</source>
        <translation>Breite des Brims, den der Slicer um Teil und Finnen auf dem Bett druckt, 0 ohne. Standfestigkeit prüfen zählt ihn zu dem, was mit ihnen auf dem Bett steht.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="243"/>
        <source>separate: fins are their own object and only touch the part; merged: fins and part become one body</source>
        <translation>getrennt: die Finnen sind ein eigenes Objekt und berühren das Bauteil nur; verbunden: Finnen und Bauteil werden ein Körper</translation>
    </message>
    <message>
        <location filename="../feature.py" line="249"/>
        <source>Clearance between fin and face, along the face normal</source>
        <translation>Abstand zwischen Finne und Fläche, senkrecht zur Fläche gemessen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="253"/>
        <source>Distance between the end of a tine and the face, along the face normal; 0 = the tine touches the face. More leaves fainter marks, too much and the tine does not hold: find the value by a test print.</source>
        <translation>Abstand zwischen dem Ende einer Zinke und der Fläche, senkrecht zur Fläche gemessen; 0 = die Zinke berührt die Fläche. Mehr hinterlässt schwächere Spuren, zu viel und die Zinke hält nicht: den Wert mit einem Probedruck finden.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="260"/>
        <source>Vertical distance between tines, at least the tine height plus one layer</source>
        <translation>Senkrechter Abstand der Zinken, mindestens die Zinkenhöhe plus eine Schicht</translation>
    </message>
    <message>
        <location filename="../feature.py" line="265"/>
        <source>Start the tine grid anew at the lower edge of the face under each fin and above every gap it bridges, so a short face or one above a hole still gets tines; off, one grid counts from the bed for every fin</source>
        <translation>Zinkenraster an der Unterkante der Fläche unter jeder Finne und über jeder Lücke, die sie überbrückt, neu beginnen, damit auch eine kurze Fläche oder eine über einem Loch Zinken bekommt; aus: ein Raster vom Bett aus für alle Finnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="272"/>
        <source>Height of the lowest tine above the bed, 0 = on the top of the foot</source>
        <translation>Höhe der untersten Zinke über dem Bett, 0 = auf der Oberkante des Fußes</translation>
    </message>
    <message>
        <location filename="../feature.py" line="276"/>
        <source>Tine height in layers</source>
        <translation>Höhe einer Zinke in Schichten</translation>
    </message>
    <message>
        <location filename="../feature.py" line="280"/>
        <source>Tine width in beads</source>
        <translation>Breite einer Zinke in Bahnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="284"/>
        <source>Number of tines per fin, 0 = as many as fit</source>
        <translation>Zinken je Finne, 0 = so viele wie passen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="288"/>
        <source>Wall thickness of a fin, 0 = from its height</source>
        <translation>Wandstärke einer Finne, 0 = aus ihrer Höhe</translation>
    </message>
    <message>
        <location filename="../feature.py" line="292"/>
        <source>Height of the fins, 0 = top of the highest tine. A lower value leaves out the tines above it; the fins reach at most to just below the top of the face.</source>
        <translation>Höhe der Finnen, 0 = Oberkante der höchsten Zinke. Ein kleinerer Wert lässt die Zinken darüber weg; die Finnen reichen höchstens bis knapp unter die Oberkante der Fläche.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="298"/>
        <source>Width of the flat top of a fin</source>
        <translation>Breite der flachen Oberseite einer Finne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="302"/>
        <source>auto: by face length; center: one fin; ends: two fins; corners: two fins on the face ends, each tine whole on the face and flush with its end, so the tine marks merge with the edges; the fin reaches a little past the end; left corner, right corner: one such fin on that end, left and right as seen from outside, looking at the face; distributed: FinCount fins</source>
        <translation>automatisch: nach Flächenlänge; mittig: eine Finne; Enden: zwei Finnen; Ecken: zwei Finnen an den Flächenenden, jede Zinke liegt ganz auf der Fläche und schließt bündig mit ihrem Ende ab, so verschwinden die Spuren der Zinken in den Kanten; die Finne ragt etwas über das Ende hinaus; linke Ecke, rechte Ecke: eine solche Finne an diesem Ende, links und rechts von außen auf die Fläche gesehen; verteilt: Anzahl Finnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="312"/>
        <source>Number of fins for distributed placement</source>
        <translation>Anzahl der Finnen bei verteilter Lage</translation>
    </message>
    <message>
        <location filename="../feature.py" line="316"/>
        <source>Distance of the outer fins from the face ends</source>
        <translation>Abstand der äußeren Finnen von den Enden der Fläche</translation>
    </message>
    <message>
        <location filename="../feature.py" line="320"/>
        <source>Automatic placement: one fin per this much face length</source>
        <translation>Automatische Lage: eine Finne je so viel Flächenlänge</translation>
    </message>
    <message>
        <location filename="../feature.py" line="324"/>
        <source>Shape of the foot on the bed</source>
        <translation>Form des Fußes auf dem Bett</translation>
    </message>
    <message>
        <location filename="../feature.py" line="328"/>
        <source>Height of the foot, rounded to whole layers</source>
        <translation>Höhe des Fußes, auf ganze Schichten gerundet</translation>
    </message>
    <message>
        <location filename="../feature.py" line="332"/>
        <source>How far the foot reaches past the outer end of the fin</source>
        <translation>Wie weit der Fuß über das äußere Ende der Finne hinausreicht</translation>
    </message>
    <message>
        <location filename="../feature.py" line="336"/>
        <source>Foot width as a share of its length</source>
        <translation>Breite des Fußes als Anteil seiner Länge</translation>
    </message>
    <message>
        <location filename="../feature.py" line="340"/>
        <source>Half width of the foot, 0 = from FootWidthRatio</source>
        <translation>Halbe Breite des Fußes, 0 = aus dem Breitenanteil</translation>
    </message>
    <message>
        <location filename="../feature.py" line="344"/>
        <source>Tines of the counter fin, 0 = as many as the main fin. The counter fin only has to stop the part from tipping over, so it may be smaller.</source>
        <translation>Zinken der Gegenfinne, 0 = so viele wie die Hauptfinne. Die Gegenfinne muss nur das Umkippen des Bauteils verhindern und darf deshalb kleiner sein.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="397"/>
        <source>Part and the face the fins support</source>
        <translation>Bauteil und die Fläche, die die Finnen stützen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="399"/>
        <source>Outermost container of the part, so moving it rebuilds the fins</source>
        <translation>Äußerster Container des Bauteils, damit ein Verschieben die Finnen neu berechnet</translation>
    </message>
    <message>
        <location filename="../feature.py" line="404"/>
        <source>Optional face on the opposite side for a small counter fin</source>
        <translation>Optionale Fläche auf der Gegenseite für eine kleine Gegenfinne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="419"/>
        <source>Faces of the part that overhang too flatly and carry no fins</source>
        <translation>Flächen des Teils, die zu flach überhängen und keine Finnen tragen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="425"/>
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
        <location filename="../check.py" line="36"/>
        <source>Check</source>
        <translation>Prüfung</translation>
    </message>
    <message>
        <location filename="../check.py" line="37"/>
        <source>Shown</source>
        <translation>Anzeige</translation>
    </message>
    <message>
        <location filename="../check.py" line="44"/>
        <source>The part checked</source>
        <translation>Das geprüfte Teil</translation>
    </message>
    <message>
        <location filename="../check.py" line="47"/>
        <source>The fins of the part checked</source>
        <translation>Die Finnen des geprüften Teils</translation>
    </message>
    <message>
        <location filename="../check.py" line="51"/>
        <source>What was checked</source>
        <translation>Was geprüft wurde</translation>
    </message>
    <message>
        <location filename="../check.py" line="53"/>
        <source>What the check found</source>
        <translation>Was die Prüfung ergab</translation>
    </message>
    <message>
        <location filename="../check.py" line="56"/>
        <source>The part, its place or its fins changed since: double-click to check again</source>
        <translation>Das Teil, seine Lage oder seine Finnen haben sich seitdem geändert: zum erneuten Prüfen doppelklicken</translation>
    </message>
</context>
<context>
    <name>FinSnap</name>
    <message>
        <location filename="../commands.py" line="47"/>
        <source>3MF files (*.3mf)</source>
        <translation>3MF-Dateien (*.3mf)</translation>
    </message>
    <message>
        <location filename="../commands.py" line="51"/>
        <source>Select a part, or its fins, to check whether it stays standing while it is printed.</source>
        <translation>Wähle ein Teil oder seine Finnen aus, um zu prüfen, ob es während des Drucks stehen bleibt.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="54"/>
        <source>Another task panel is open. Close it first, then make the fins again.</source>
        <translation>Ein anderes Aufgabenfenster ist offen. Schließe es zuerst und erzeuge die Finnen dann erneut.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="248"/>
        <source>Remove fin</source>
        <translation>Finne entfernen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="331"/>
        <source>Select one edge of the part, and the face of that edge that is to lie on the bed; or a face alone, a chamfer or a fillet; or the two faces beside it.</source>
        <translation>Wähle eine Kante des Teils und die Fläche dieser Kante, die auf dem Bett liegen soll; oder eine Fläche allein, eine Fase oder eine Verrundung; oder die beiden Flächen daneben.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="351"/>
        <location filename="../commands.py" line="362"/>
        <source>Stand on edge</source>
        <translation>Auf Kante stellen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="352"/>
        <source>Tilt angle (degrees):</source>
        <translation>Kippwinkel (Grad):</translation>
    </message>
    <message>
        <location filename="../commands.py" line="419"/>
        <source>%d faces overhang flatter than %.0f degrees from the bed and are selected: they need fins or support.</source>
        <translation>%d Flächen hängen flacher als %.0f Grad zur Bettebene über und sind ausgewählt: sie brauchen Finnen oder Stützen.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="478"/>
        <source>Lay flat again</source>
        <translation>Wieder flach legen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="497"/>
        <source>Delete the fins of the part as well? No keeps them, moved along with the part, and rebuilds them once it is moved again, for example stood on its edge.</source>
        <translation>Die Finnen des Teils auch löschen? Nein behält sie, mit dem Teil mitbewegt, und baut sie neu, sobald es wieder bewegt wird, etwa auf die Kante gestellt.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="538"/>
        <source>Select an edge or a face of one part.</source>
        <translation>Wähle eine Kante oder eine Fläche eines Teils.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="874"/>
        <source>nothing to export: the parts of %s lie flat; stand them on their edge again</source>
        <translation>nichts zu exportieren: die Teile von %s liegen flach; stelle sie wieder auf die Kante</translation>
    </message>
    <message>
        <location filename="../commands.py" line="989"/>
        <source>Left out, as their part lies flat: %s. Stand it on its edge again to export these fins.</source>
        <translation>Ausgelassen, weil ihr Teil flach liegt: %s. Stelle es wieder auf die Kante, um diese Finnen zu exportieren.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="463"/>
        <source>The selection was not stood on an edge with Stand on edge.</source>
        <translation>Die Auswahl wurde nicht mit Auf Kante stellen aufgestellt.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="49"/>
        <source>STEP files (*.step *.stp)</source>
        <translation>STEP-Dateien (*.step *.stp)</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1446"/>
        <source>This edge does not lie on the bed, and its faces do not meet at a right angle. Use Stand on edge with the edge and the face that is to lie on the bed, then Add fins.</source>
        <translation>Diese Kante liegt nicht auf dem Bett, und ihre Flächen treffen sich nicht im rechten Winkel. Nimm „Auf Kante stellen“ mit der Kante und der Fläche, die auf das Bett soll, und danach „Finnen hinzufügen“.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="555"/>
        <source>Quick fins</source>
        <translation>Schnelle Finnen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="749"/>
        <source>Select one face to support, or two faces for a counter fin.</source>
        <translation>Eine Fläche zum Stützen auswählen, oder zwei Flächen für eine Gegenfinne.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="754"/>
        <source>Add fins</source>
        <translation>Finnen hinzufügen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="789"/>
        <source>Select one fin object, and optionally one face of its part.</source>
        <translation>Ein Finnen-Objekt auswählen, optional dazu eine Fläche seines Bauteils.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="792"/>
        <source>The face for the counter fin has to belong to the part the fins stand under.</source>
        <translation>Die Fläche für die Gegenfinne muss zu dem Teil gehören, unter dem die Finnen stehen.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="795"/>
        <location filename="../taskpanel.py" line="720"/>
        <source>Add counter fin</source>
        <translation>Gegenfinne hinzufügen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="107"/>
        <source>No counter fin on this face: %s</source>
        <translation>Keine Gegenfinne auf dieser Fläche: %s</translation>
    </message>
    <message>
        <location filename="../commands.py" line="883"/>
        <source>Mesh fineness</source>
        <translation>Netzfeinheit</translation>
    </message>
    <message>
        <location filename="../commands.py" line="891"/>
        <source>Surface deviation</source>
        <translation>Oberflächenabweichung</translation>
    </message>
    <message>
        <location filename="../commands.py" line="898"/>
        <source>Angular deviation</source>
        <translation>Winkelabweichung</translation>
    </message>
    <message>
        <location filename="../commands.py" line="900"/>
        <source>Planar faces are exported exactly; these values only affect curved surfaces.</source>
        <translation>Ebene Flächen werden exakt exportiert; diese Werte wirken nur auf gekrümmte Flächen.</translation>
    </message>
    <message>
        <location filename="../commands.py" line="935"/>
        <source>Export 3MF</source>
        <translation>3MF exportieren</translation>
    </message>
    <message>
        <location filename="../commands.py" line="958"/>
        <source>Export STEP</source>
        <translation>STEP exportieren</translation>
    </message>
    <message>
        <location filename="../feature.py" line="170"/>
        <source>Enter the values of the print profile you will slice with. Tines and fin are sized in beads and layers of this profile.</source>
        <translation>Die Werte des Druckprofils eintragen, mit dem gesliced wird. Zinken und Finne werden in Bahnen und Schichten dieses Profils bemessen.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="125"/>
        <source>The part lies flat again: the fins keep their last shape until the part is moved, for example stood on its edge again; then they are rebuilt.</source>
        <translation>Das Teil liegt wieder flach: Die Finnen behalten ihre letzte Form, bis das Teil bewegt wird, etwa wieder auf die Kante gestellt; dann werden sie neu gebaut.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="39"/>
        <source>%d faces of %s overhang flatter than %.0f degrees from the bed without fins: %s</source>
        <translation>%d Flächen von %s hängen flacher als %.0f Grad zur Bettebene über und tragen keine Finnen: %s</translation>
    </message>
    <message>
        <location filename="../feature.py" line="41"/>
        <source>%d faces of %s overhang flatter than %.0f degrees from the bed without fins, too flat to print: %s</source>
        <translation>%d Flächen von %s hängen flacher als %.0f Grad zur Bettebene über und tragen keine Finnen, zu flach zum Drucken: %s</translation>
    </message>
    <message>
        <location filename="../feature.py" line="82"/>
        <source>The number of fins changed, so the fins changed by hand are as planned again: removed fins are back, moved fins and fin heights of their own are undone.</source>
        <translation>Die Zahl der Finnen hat sich geändert, deshalb sind die von Hand geänderten Finnen wieder wie geplant: entfernte Finnen sind zurück, Verschiebungen und eigene Höhen sind aufgehoben.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="85"/>
        <source>The tines lie at other heights now, so fin heights of their own are undone: each fin ends at its highest tine again.</source>
        <translation>Die Zinken liegen jetzt auf anderen Höhen, deshalb sind die eigenen Finnenhöhen zurückgesetzt: jede Finne endet wieder an ihrer obersten Zinke.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="103"/>
        <source>Single fins can be removed with the separate connection only; merged into the part they have no body of their own. To delete all of them, select the fins in the tree.</source>
        <translation>Einzelne Finnen lassen sich nur mit der getrennten Verbindung entfernen; mit dem Teil verschmolzen haben sie keinen eigenen Körper. Um alle zu löschen, wähle die Finnen im Baum.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="109"/>
        <source>The part has no face leaning the other way that takes a counter fin. Select one yourself.</source>
        <translation>Das Teil hat keine Fläche, die sich andersherum neigt und eine Gegenfinne trägt. Wähle selbst eine aus.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="113"/>
        <source>%s is the seam between two halves of a side; select the side or its rim instead</source>
        <translation>%s ist die Naht zwischen zwei Hälften einer Seite; wähle stattdessen die Seite oder ihren Rand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="117"/>
        <source>the face the fins stand under is gone from %s: select a face for them again</source>
        <translation>die Fläche, unter der die Finnen stehen, gibt es an %s nicht mehr: wähle erneut eine Fläche für sie</translation>
    </message>
    <message>
        <location filename="../feature.py" line="120"/>
        <source>%s of the joined part matches no face of the part itself</source>
        <translation>%s des zusammengefügten Teils passt zu keiner Fläche des Teils selbst</translation>
    </message>
    <message>
        <location filename="../feature.py" line="173"/>
        <source>Separate keeps the fins a separate object that only touches the part and breaks off cleanly. Merged prints fins and part as one body. A tine clearance keeps the ends of the tines that far from the face.</source>
        <translation>Getrennt hält die Finnen als eigenes Objekt, das das Bauteil nur berührt und sauber abbricht. Verbunden druckt Finnen und Bauteil als einen Körper. Ein Zinkenabstand hält die Enden der Zinken so weit von der Fläche fern.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="177"/>
        <source>Tines are the small horizontal contacts between fin and part. The highest tine sets the height of the fin.</source>
        <translation>Zinken sind die kleinen waagerechten Kontakte zwischen Finne und Bauteil. Die höchste Zinke bestimmt die Höhe der Finne.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="180"/>
        <source>0 means automatic: the thickness grows with the height, the height ends at the highest tine.</source>
        <translation>0 heißt automatisch: die Dicke wächst mit der Höhe, die Höhe endet an der höchsten Zinke.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="183"/>
        <source>Automatic places one fin per face length set below, a single fin in the centre.</source>
        <translation>Automatisch setzt eine Finne je unten eingestellter Flächenlänge, eine einzelne Finne mittig.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="186"/>
        <source>The foot holds the fin on the bed. It is narrowed automatically so that the feet of neighbouring fins never touch.</source>
        <translation>Der Fuß hält die Finne auf dem Bett. Er wird automatisch schmaler, damit sich die Füße benachbarter Finnen nie berühren.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="189"/>
        <source>A fin on the opposite face, against tipping away, as large as the main fin. It only has to stop the part from tipping over, so fewer tines are enough to make it smaller. Add it with Add counter fin, or select a second face when adding the fins.</source>
        <translation>Eine Finne auf der Gegenseite gegen Wegkippen, so groß wie die Hauptfinne. Sie muss nur das Umkippen verhindern, weniger Zinken machen sie kleiner. Mit Gegenfinne hinzufügen ergänzen, oder beim Hinzufügen der Finnen eine zweite Fläche auswählen.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="204"/>
        <source>separate, touching only</source>
        <translation>getrennt, nur berührend</translation>
    </message>
    <message>
        <location filename="../feature.py" line="205"/>
        <source>merged into the part</source>
        <translation>mit dem Bauteil verbunden</translation>
    </message>
    <message>
        <location filename="../feature.py" line="206"/>
        <source>automatic</source>
        <translation>automatisch</translation>
    </message>
    <message>
        <location filename="../feature.py" line="207"/>
        <source>one in the centre</source>
        <translation>eine mittig</translation>
    </message>
    <message>
        <location filename="../feature.py" line="208"/>
        <source>two at the ends</source>
        <translation>zwei an den Enden</translation>
    </message>
    <message>
        <location filename="../feature.py" line="209"/>
        <source>two on the corners</source>
        <translation>zwei auf den Ecken</translation>
    </message>
    <message>
        <location filename="../feature.py" line="210"/>
        <source>one on the left corner</source>
        <translation>eine auf der linken Ecke</translation>
    </message>
    <message>
        <location filename="../feature.py" line="211"/>
        <source>one on the right corner</source>
        <translation>eine auf der rechten Ecke</translation>
    </message>
    <message>
        <location filename="../feature.py" line="212"/>
        <source>distributed</source>
        <translation>verteilt</translation>
    </message>
    <message>
        <location filename="../feature.py" line="213"/>
        <source>oval</source>
        <translation>oval</translation>
    </message>
    <message>
        <location filename="../feature.py" line="214"/>
        <source>rectangle</source>
        <translation>rechteckig</translation>
    </message>
    <message>
        <location filename="../feature.py" line="215"/>
        <source>none</source>
        <translation>keiner</translation>
    </message>
    <message>
        <location filename="../feature.py" line="221"/>
        <source>Nozzle diameter</source>
        <translation>Düsendurchmesser</translation>
    </message>
    <message>
        <location filename="../feature.py" line="225"/>
        <source>Bead width</source>
        <translation>Bahnbreite</translation>
    </message>
    <message>
        <location filename="../feature.py" line="229"/>
        <source>Layer height</source>
        <translation>Schichthöhe</translation>
    </message>
    <message>
        <location filename="../feature.py" line="233"/>
        <source>First layer height</source>
        <translation>Höhe der ersten Schicht</translation>
    </message>
    <message>
        <location filename="../feature.py" line="237"/>
        <source>Brim width</source>
        <translation>Brim-Breite</translation>
    </message>
    <message>
        <location filename="../feature.py" line="242"/>
        <source>Connection</source>
        <translation>Verbindung</translation>
    </message>
    <message>
        <location filename="../feature.py" line="248"/>
        <source>Gap</source>
        <translation>Spalt</translation>
    </message>
    <message>
        <location filename="../feature.py" line="252"/>
        <source>Tine clearance</source>
        <translation>Zinkenabstand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="259"/>
        <source>Tine spacing</source>
        <translation>Zinkenabstand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="264"/>
        <source>Restart tines after a gap</source>
        <translation>Zinken nach Lücke neu beginnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="271"/>
        <source>Tine first</source>
        <translation>Erste Zinke</translation>
    </message>
    <message>
        <location filename="../feature.py" line="275"/>
        <source>Tine layers</source>
        <translation>Zinkenhöhe in Schichten</translation>
    </message>
    <message>
        <location filename="../feature.py" line="279"/>
        <source>Tine width beads</source>
        <translation>Zinkenbreite in Bahnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="283"/>
        <source>Tine count</source>
        <translation>Zinkenanzahl</translation>
    </message>
    <message>
        <location filename="../feature.py" line="287"/>
        <source>Fin thickness</source>
        <translation>Finnendicke</translation>
    </message>
    <message>
        <location filename="../feature.py" line="291"/>
        <source>Fin height</source>
        <translation>Finnenhöhe</translation>
    </message>
    <message>
        <location filename="../feature.py" line="297"/>
        <source>Top width</source>
        <translation>Breite der Oberseite</translation>
    </message>
    <message>
        <location filename="../feature.py" line="301"/>
        <source>Fin placement</source>
        <translation>Lage der Finnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="311"/>
        <source>Fin count</source>
        <translation>Anzahl Finnen</translation>
    </message>
    <message>
        <location filename="../feature.py" line="315"/>
        <source>End inset</source>
        <translation>Randabstand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="319"/>
        <source>Face length per fin</source>
        <translation>Flächenlänge je Finne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="323"/>
        <source>Foot shape</source>
        <translation>Fußform</translation>
    </message>
    <message>
        <location filename="../feature.py" line="327"/>
        <source>Foot thickness</source>
        <translation>Fußhöhe</translation>
    </message>
    <message>
        <location filename="../feature.py" line="331"/>
        <source>Foot overhang</source>
        <translation>Fußüberstand</translation>
    </message>
    <message>
        <location filename="../feature.py" line="335"/>
        <source>Foot width ratio</source>
        <translation>Breitenanteil des Fußes</translation>
    </message>
    <message>
        <location filename="../feature.py" line="339"/>
        <source>Foot half width</source>
        <translation>Halbe Fußbreite</translation>
    </message>
    <message>
        <location filename="../feature.py" line="343"/>
        <source>Counter tine count</source>
        <translation>Zinken der Gegenfinne</translation>
    </message>
    <message>
        <location filename="../feature.py" line="355"/>
        <source>Not used without a foot.</source>
        <translation>Ohne Fuß nicht verwendet.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="358"/>
        <source>Only used with distributed placement.</source>
        <translation>Nur bei verteilter Platzierung verwendet.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="360"/>
        <source>Only used with automatic placement.</source>
        <translation>Nur bei automatischer Platzierung verwendet.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="362"/>
        <source>Not used with one fin in the centre or fins on the corners.</source>
        <translation>Nicht verwendet bei einer Finne in der Mitte oder Finnen auf den Ecken.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="368"/>
        <source>Only used while Foot half width is 0.</source>
        <translation>Nur verwendet, solange Halbe Fußbreite 0 ist.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="370"/>
        <source>Only used with a counter fin.</source>
        <translation>Nur mit Gegenfinne verwendet.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="372"/>
        <source>Not used with fins merged into the part: they need their tines on the face, or they would be loose bodies.</source>
        <translation>Nicht verwendet bei Finnen, die mit dem Teil verschmolzen werden: Ihre Zinken müssen auf der Fläche sitzen, sonst wären sie lose Körper.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="452"/>
        <source>no face selected on %s</source>
        <translation>keine Fläche an %s gewählt</translation>
    </message>
    <message>
        <location filename="../feature.py" line="687"/>
        <source>Nothing of the part stands on the bed.</source>
        <translation>Nichts von dem Teil steht auf dem Bett.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="688"/>
        <source>Stands on its own while it is printed: at least %.1f mm from tipping, at layer %d (%.1f mm).</source>
        <translation>Steht während des Drucks von allein: mindestens %.1f mm vom Kippen entfernt, bei Schicht %d (%.1f mm).</translation>
    </message>
    <message>
        <location filename="../feature.py" line="690"/>
        <source>Stands on its own, but only just: %.1f mm from tipping at layer %d (%.1f mm).</source>
        <translation>Steht von allein, aber nur knapp: %.1f mm vom Kippen entfernt bei Schicht %d (%.1f mm).</translation>
    </message>
    <message>
        <location filename="../feature.py" line="692"/>
        <source>Tips over at layer %d (%.1f mm) while it is printed: fins under its leaning face hold it.</source>
        <translation>Kippt während des Drucks bei Schicht %d (%.1f mm) um: Finnen unter seiner geneigten Fläche halten es.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="694"/>
        <source>On its own it would tip over at layer %d (%.1f mm); its fins hold it: at least %.1f mm from tipping, at layer %d (%.1f mm).</source>
        <translation>Allein würde es bei Schicht %d (%.1f mm) umkippen; seine Finnen halten es: mindestens %.1f mm vom Kippen entfernt, bei Schicht %d (%.1f mm).</translation>
    </message>
    <message>
        <location filename="../feature.py" line="697"/>
        <source>On its own it would tip over at layer %d (%.1f mm); its fins hold it, but only just: %.1f mm from tipping at layer %d (%.1f mm).</source>
        <translation>Allein würde es bei Schicht %d (%.1f mm) umkippen; seine Finnen halten es, aber nur knapp: %.1f mm vom Kippen entfernt bei Schicht %d (%.1f mm).</translation>
    </message>
    <message>
        <location filename="../feature.py" line="700"/>
        <source>Tips over at layer %d (%.1f mm), before its fins hold it from their lowest tine at %.1f mm: set the first tine lower.</source>
        <translation>Kippt bei Schicht %d (%.1f mm) um, bevor seine Finnen es ab ihrer untersten Zinke bei %.1f mm halten: setze die erste Zinke tiefer.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="703"/>
        <source>Tips over at layer %d (%.1f mm), away from its fins: a counter fin on that side holds it.</source>
        <translation>Kippt bei Schicht %d (%.1f mm) von seinen Finnen weg um: eine Gegenfinne auf dieser Seite hält es.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="705"/>
        <source>Tips over at layer %d (%.1f mm) towards its fins, past their feet: a longer foot or more fins hold it.</source>
        <translation>Kippt bei Schicht %d (%.1f mm) zu seinen Finnen hin um, über ihre Füße hinaus: ein längerer Fuß oder mehr Finnen halten es.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="708"/>
        <source>Tips over at layer %d (%.1f mm), past an end of the edge it stands on.</source>
        <translation>Kippt bei Schicht %d (%.1f mm) über ein Ende der Kante um, auf der es steht.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="991"/>
        <source>Main fin: %s</source>
        <translation>Hauptfinne: %s</translation>
    </message>
    <message>
        <location filename="../feature.py" line="959"/>
        <location filename="../feature.py" line="995"/>
        <source>Counter fin: %s</source>
        <translation>Gegenfinne: %s</translation>
    </message>
    <message>
        <location filename="../feature.py" line="53"/>
        <source>%d island(s): %s would start printing in the air there, on no layer of it below. Fins do not carry an island, they only keep the part from falling over. It cannot print standing so; the islands are marked in the 3D view.</source>
        <translation>%d Insel(n): %s würde dort in der Luft zu drucken beginnen, ohne eigene Schicht darunter. Finnen tragen keine Insel, sie halten das Teil nur gegen Umfallen. So aufgestellt lässt es sich nicht drucken; die Inseln sind in der 3D-Ansicht markiert.</translation>
    </message>
    <message>
        <location filename="../feature.py" line="123"/>
        <source>the counter fin goes under a flat face, not under the side of a cylinder or tube</source>
        <translation>die Gegenfinne gehört unter eine ebene Fläche, nicht unter die Seite eines Zylinders oder Rohrs</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="658"/>
        <source>FinSnap parameters</source>
        <translation>FinSnap-Parameter</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="179"/>
        <source>Side view</source>
        <translation>Seitenansicht</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="95"/>
        <source>Main fin</source>
        <translation>Hauptfinne</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="96"/>
        <source>Counter fin</source>
        <translation>Gegenfinne</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="180"/>
        <source>Top view</source>
        <translation>Draufsicht</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="662"/>
        <source>Hover over a field for an explanation. Letters in brackets point to the drawings below. Every change is shown in the 3D view right away. Greyed-out fields have no effect with the current choices; their tooltip says why.</source>
        <translation>Für eine Erklärung mit der Maus über ein Feld fahren. Buchstaben in Klammern verweisen auf die Zeichnungen unten. Jede Änderung erscheint sofort in der 3D-Ansicht. Ausgegraute Felder wirken bei der aktuellen Wahl nicht; ihr Tooltip sagt, warum.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="119"/>
        <source>Edit fins</source>
        <translation>Finnen bearbeiten</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="709"/>
        <source>To remove one fin, click it in the 3D view and press Remove selected fin, or the Delete key. The counter fin goes on the face leaning the other way, or on a face of the part you select. Drag the two arrows on a fin to move it along the face or to change its height, or type the values below; click another fin, or pick it in the list of fins, to put the arrows there. Reset fins undoes every change by hand.</source>
        <translation>Um eine einzelne Finne zu entfernen, klicke sie in der 3D-Ansicht an und drücke „Gewählte Finne entfernen“ oder die Entf-Taste. Die Gegenfinne kommt auf die Fläche, die sich zur anderen Seite neigt, oder auf eine Fläche des Teils, die du wählst. Ziehe an den beiden Pfeilen einer Finne, um sie entlang der Fläche zu verschieben oder ihre Höhe zu ändern, oder tippe die Werte unten ein; klicke eine andere Finne an oder wähle sie in der Liste der Finnen, um die Pfeile dorthin zu setzen. „Finnen zurücksetzen“ nimmt jede Änderung von Hand zurück.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="718"/>
        <source>Remove selected fin</source>
        <translation>Gewählte Finne entfernen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="721"/>
        <source>Remove counter fin</source>
        <translation>Gegenfinne entfernen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="729"/>
        <source>The fins, the main fins from the left, then the counter fins. Pick one to put the arrows on it and select it.</source>
        <translation>Die Finnen, erst die Hauptfinnen von links, dann die Gegenfinnen. Wähle eine aus, um die Pfeile auf sie zu setzen und sie auszuwählen.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="79"/>
        <source>Place on the face</source>
        <translation>Lage auf der Fläche</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="47"/>
        <source>on</source>
        <translation>an</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="48"/>
        <source>off</source>
        <translation>aus</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="84"/>
        <source>Angle on the part</source>
        <translation>Winkel am Teil</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="89"/>
        <source>Height</source>
        <translation>Höhe</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="141"/>
        <source>Stand the part another way? The fins are planned anew: fins removed, moved or set to a height of their own, a turn of the part and the counter fin are undone.</source>
        <translation>Das Teil anders aufstellen? Die Finnen werden neu geplant: entfernte, verschobene Finnen und eigene Höhen, eine Drehung des Teils und die Gegenfinne werden aufgehoben.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="165"/>
        <source>No face overhangs without fins.</source>
        <translation>Keine Fläche hängt ohne Finnen über.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="166"/>
        <source>%d island(s): it would start printing in the air there.</source>
        <translation>%d Insel(n): dort würde es in der Luft zu drucken beginnen.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="167"/>
        <source>No islands.</source>
        <translation>Keine Inseln.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="171"/>
        <source>Checks whether the part stays standing while it is printed, layer by layer, on its own and held by these fins, which hold it only from their lowest tine up, and shows the plumb line from its centre of mass to the bed. Takes a moment on a large part.</source>
        <translation>Prüft Schicht für Schicht, ob das Teil während des Drucks stehen bleibt, allein und von diesen Finnen gehalten, die es erst ab ihrer untersten Zinke halten, und zeigt das Lot von seinem Schwerpunkt zum Bett. Dauert bei einem großen Teil einen Moment.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="175"/>
        <source>Changed since the stability check: check again.</source>
        <translation>Seit der Prüfung der Standfestigkeit geändert: erneut prüfen.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="177"/>
        <source>The part of this check is gone; delete the check.</source>
        <translation>Das Teil dieser Prüfung gibt es nicht mehr; lösche die Prüfung.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="757"/>
        <source>Save as standard</source>
        <translation>Als Standard speichern</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="758"/>
        <source>New fins start with these values. Fields that differ from the standard are marked, and their button puts the standard back.</source>
        <translation>Neue Finnen starten mit diesen Werten. Felder, die vom Standard abweichen, sind markiert, und ihr Knopf stellt den Standard wieder her.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="762"/>
        <location filename="../taskpanel.py" line="928"/>
        <source>Factory settings</source>
        <translation>Werkseinstellungen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="763"/>
        <source>Forget the saved standard and set every field to the built-in value.</source>
        <translation>Den gespeicherten Standard verwerfen und jedes Feld auf den eingebauten Wert setzen.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="783"/>
        <source>Check stability</source>
        <translation>Standfestigkeit prüfen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="840"/>
        <source>Stand another way</source>
        <translation>Anders aufstellen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="908"/>
        <source>Back to the standard: %s</source>
        <translation>Zurück auf den Standard: %s</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="929"/>
        <source>Forget the saved standard and set every field to the built-in value?</source>
        <translation>Den gespeicherten Standard verwerfen und jedes Feld auf den eingebauten Wert setzen?</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="957"/>
        <location filename="../taskpanel.py" line="961"/>
        <source>Nothing removed</source>
        <translation>Nichts entfernt</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="968"/>
        <source>Delete the fins?</source>
        <translation>Finnen löschen?</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="969"/>
        <source>These are the last fins. Delete the fins object? A part stood on an edge for these fins alone is laid flat again.</source>
        <translation>Das sind die letzten Finnen. Das Finnen-Objekt löschen? Ein Teil, das nur für diese Finnen auf eine Kante gestellt wurde, wird wieder flach gelegt.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="985"/>
        <source>Delete fins</source>
        <translation>Finnen löschen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1134"/>
        <source>%s %d</source>
        <translation>%s %d</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="417"/>
        <source>Cancel fins</source>
        <translation>Finnen abbrechen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="75"/>
        <source>Click a fin of these fins in the 3D view first.</source>
        <translation>Klicke zuerst eine dieser Finnen in der 3D-Ansicht an.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="80"/>
        <source>Distance of the middle of the fin from the left end of the face, seen from outside. Type a value to move the fin there.</source>
        <translation>Abstand der Mitte der Finne vom linken Ende der Fläche, von außen gesehen. Wert eingeben, um die Finne dorthin zu verschieben.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="85"/>
        <source>Position of the fin around the cylinder or tube, measured at the middle of its tines, in degrees from 0°, where it is first placed. Type a value to turn the part to it; the fin keeps its place.</source>
        <translation>Position der Finne am Umfang des Zylinders oder Rohrs, gemessen an der Mitte der Zinken, in Grad ab 0°, wo sie zuerst gesetzt wird. Wert eingeben, um das Teil dorthin zu drehen; die Finne bleibt an ihrem Platz.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="90"/>
        <source>Height of this fin alone. Type a value to set it; Reset fins gives it the height of the others again.</source>
        <translation>Höhe nur dieser Finne. Wert eingeben, um sie zu setzen; Finnen zurücksetzen gibt ihr wieder die Höhe der anderen.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="129"/>
        <source>Stand</source>
        <translation>Aufstellung</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="132"/>
        <source>Stands on</source>
        <translation>Steht auf</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="132"/>
        <source>Length</source>
        <translation>Länge</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="133"/>
        <location filename="../taskpanel.py" line="135"/>
        <source>Islands</source>
        <translation>Inseln</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="134"/>
        <source>Fins under</source>
        <translation>Finnen unter</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="134"/>
        <source>Area</source>
        <translation>Flächeninhalt</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="137"/>
        <source>Quick fins found more than one way to stand the part. Click a row to stand it so; the part and its fins follow in the 3D view. Ways where the part would start printing in the air, an island, are left out while one without is found.</source>
        <translation>Schnelle Finnen hat mehr als eine Möglichkeit gefunden, das Teil aufzustellen. Klicke eine Zeile an, um es so aufzustellen; Teil und Finnen folgen in der 3D-Ansicht. Möglichkeiten, bei denen das Teil in der Luft zu drucken beginnen würde, eine Insel, werden weggelassen, solange es eine ohne gibt.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="151"/>
        <source>Tips at layer %d, %.1f mm high</source>
        <translation>Kippt bei Schicht %d, %.1f mm hoch</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="152"/>
        <source>Closest to tipping at layer %d, %.1f mm high</source>
        <translation>Am knappsten bei Schicht %d, %.1f mm hoch</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="154"/>
        <source>Colours by height: green stands, yellow comes within %.0f mm of tipping, red tips from there.</source>
        <translation>Farben nach Höhe: grün steht, gelb kommt dem Kippen auf weniger als %.0f mm nahe, rot kippt ab dort.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="161"/>
        <source>%d faces overhang flatter than %.0f degrees from the bed without fins.</source>
        <translation>%d Flächen hängen flacher als %.0f Grad zur Bettebene über, ohne Finnen.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="163"/>
        <source>%d faces overhang flatter than %.0f degrees from the bed without fins, too flat to print.</source>
        <translation>%d Flächen hängen flacher als %.0f Grad zur Bettebene über, ohne Finnen, zu flach zum Drucken.</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="719"/>
        <source>Reset fins</source>
        <translation>Finnen zurücksetzen</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1004"/>
        <location filename="../taskpanel.py" line="1008"/>
        <source>No counter fin</source>
        <translation>Keine Gegenfinne</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1334"/>
        <source>no tine of the fin finds the face there</source>
        <translation>dort trifft keine Zinke der Finne die Fläche</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1678"/>
        <source>Not possible</source>
        <translation>Nicht möglich</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1724"/>
        <source>Notes</source>
        <translation>Hinweise</translation>
    </message>
    <message>
        <location filename="../taskpanel.py" line="1717"/>
        <source>%d fin(s), %.2f mm high, %.2f mm thick</source>
        <translation>%d Finne(n), %.2f mm hoch, %.2f mm dick</translation>
    </message>
    <message>
        <location filename="../export_3mf.py" line="74"/>
        <source>mesh deviation and angle must be greater than 0</source>
        <translation>Netzabweichung und Winkel müssen größer als 0 sein</translation>
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
        <location filename="../geometry.py" line="457"/>
        <source>the selected face is not planar</source>
        <translation>die gewählte Fläche ist nicht eben</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="368"/>
        <location filename="../geometry.py" line="461"/>
        <source>the selected face does not lean over the bed</source>
        <translation>die gewählte Fläche hängt nicht über das Bett, sie zeigt nach oben oder zur Seite</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="371"/>
        <location filename="../geometry.py" line="463"/>
        <source>the selected face is flat; it rests on the bed or needs regular support</source>
        <translation>die gewählte Fläche liegt waagerecht; sie liegt auf dem Bett oder braucht normale Stützen</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="382"/>
        <source>the selected face curves inward; fins go under the outside of a cylinder or tube</source>
        <translation>die gewählte Fläche wölbt sich nach innen; Finnen kommen unter die Außenseite eines Zylinders oder Rohrs</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="387"/>
        <source>the lowest line of the selected face is cut away</source>
        <translation>die unterste Linie der gewählten Fläche ist weggeschnitten</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="481"/>
        <source>fin_height %.2f reaches above the face (%.2f)</source>
        <translation>Finnenhöhe %.2f reicht über die Fläche hinaus (%.2f)</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="502"/>
        <source>no tine fits below %.2f mm</source>
        <translation>unter %.2f mm passt keine Zinke</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="504"/>
        <source>only %d of %d tines fit below %.2f mm</source>
        <translation>nur %d von %d Zinken passen unter %.2f mm</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="613"/>
        <source>the face is narrower than the %.2f mm a fin needs at every tine</source>
        <translation>die Fläche ist an jeder Zinke schmaler als die %.2f mm, die eine Finne braucht</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="641"/>
        <source>the face is too short for a fin on each corner</source>
        <translation>die Fläche ist zu kurz für eine Finne auf jeder Ecke</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="647"/>
        <source>the face is too short for a fin of %.2f mm</source>
        <translation>die Fläche ist zu kurz für eine Finne von %.2f mm</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="665"/>
        <source>%d fins do not fit side by side on this face</source>
        <translation>%d Finnen passen nicht nebeneinander unter diese Fläche</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="961"/>
        <source>the fins overlap the part by %.4f mm3</source>
        <translation>die Finnen überschneiden das Teil um %.4f mm³</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="996"/>
        <source>fins under the selected face alone, not reaching over the groove: %s</source>
        <translation>Finnen nur unter der gewählten Fläche, nicht über die Rille hinweg: %s</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1020"/>
        <location filename="../params.py" line="126"/>
        <source>tines (%.2f mm) are wider than the fin (%.2f mm)</source>
        <translation>die Zinken (%.2f mm) sind breiter als die Finne (%.2f mm)</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1056"/>
        <source>fin %d would pass fin %d; a fin stays between its neighbours</source>
        <translation>die Finne %d käme an der Finne %d vorbei; eine Finne bleibt zwischen ihren Nachbarinnen</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1059"/>
        <source>fins %d and %d stand %.2f mm apart, closer than %.2f mm</source>
        <translation>die Finnen %d und %d stehen %.2f mm auseinander, näher als %.2f mm</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1100"/>
        <source>fin %d is %.2f mm high, above the face (%.2f mm)</source>
        <translation>die Finne %d ist %.2f mm hoch, höher als die Fläche (%.2f mm)</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1104"/>
        <source>fin %d is lower than its first tine</source>
        <translation>die Finne %d ist niedriger als ihre erste Zinke</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1062"/>
        <source>every fin is removed; delete the fins instead, or bring them back</source>
        <translation>alle Finnen sind entfernt; lösche stattdessen die Finnen oder hole sie zurück</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1198"/>
        <source>fins moved along the face to where their tines rest, beside a hole or recess under their planned place: %s</source>
        <translation>Finnen entlang der Fläche dorthin gerückt, wo ihre Zinken aufliegen, neben ein Loch oder eine Vertiefung unter ihrem geplanten Platz: %s</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1200"/>
        <source>fin %d by %.2f mm</source>
        <translation>Finne %d um %.2f mm</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1207"/>
        <source>tines at %s mm above the bed left out: the face is narrower there than the fin</source>
        <translation>Zinken bei %s mm über dem Bett weggelassen: die Fläche ist dort schmaler als die Finne</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1221"/>
        <source>the part stands on one point of its rim: a chamfer on the rim and a brim in the slicer give it more hold on the bed</source>
        <translation>das Teil steht auf einem Punkt seines Rands: eine Fase am Rand und ein Brim im Slicer geben ihm mehr Halt auf dem Bett</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="136"/>
        <source>no face of the part leans over the bed and takes fins</source>
        <translation>keine Fläche des Teils hängt über das Bett und nimmt Finnen auf</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="137"/>
        <source>the part cannot stand so that this face takes fins</source>
        <translation>das Teil lässt sich nicht so aufstellen, dass diese Fläche Finnen aufnimmt</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1475"/>
        <source>Select an edge or a face, a face and the edge or the chamfer or fillet it is to stand on, or the two faces beside a fillet.</source>
        <translation>Wähle eine Kante oder eine Fläche, eine Fläche und die Kante oder die Fase oder Rundung, auf der sie stehen soll, oder die beiden Flächen neben einer Rundung.</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1556"/>
        <source>the fins do not fit under the selected face standing this way: %s</source>
        <translation>die Finnen passen in dieser Lage nicht unter die gewählte Fläche: %s</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1136"/>
        <source>no tine finds the face; it has a recess or hole at every tine</source>
        <translation>keine Zinke trifft die Fläche; sie hat an jeder Zinke eine Aussparung oder ein Loch</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="966"/>
        <source>a fin comes within %.3f mm of the part, closer than the %.3f mm it keeps from the face</source>
        <translation>eine Finne kommt dem Teil bis auf %.3f mm nahe, näher als die %.3f mm, die sie von der Fläche hält</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1194"/>
        <source>tines at %s mm above the bed left out: a recess or hole in the face lies under them</source>
        <translation>Zinken bei %s mm über dem Bett weggelassen: unter ihnen liegt eine Aussparung oder ein Loch in der Fläche</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1203"/>
        <source>fins at %s mm from the end of the face left out: none of their tines lies wholly on the face</source>
        <translation>Finnen bei %s mm vom Ende der Fläche weggelassen: keine ihrer Zinken liegt ganz auf der Fläche</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1212"/>
        <source>the face is inclined %.0f degrees against the bed, outside %.0f to %.0f</source>
        <translation>die Fläche ist %.0f Grad gegen das Bett geneigt, außerhalb von %.0f bis %.0f</translation>
    </message>
    <message>
        <location filename="../geometry.py" line="1217"/>
        <source>tines are %.2f mm long, shorter than %.2f beads; the slicer may not print them to the face</source>
        <translation>die Zinken sind %.2f mm lang, kürzer als %.2f Bahnen; der Slicer druckt sie womöglich nicht bis an die Fläche</translation>
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
        <location filename="../orient.py" line="354"/>
        <source>the tilt angle must lie between 0 and 90 degrees</source>
        <translation>der Kippwinkel muss zwischen 0 und 90 Grad liegen</translation>
    </message>
    <message>
        <location filename="../orient.py" line="360"/>
        <source>the edge is curved; select a straight edge</source>
        <translation>die Kante ist gekrümmt; wähle eine gerade Kante</translation>
    </message>
    <message>
        <location filename="../orient.py" line="362"/>
        <source>the edge is not horizontal</source>
        <translation>die Kante liegt nicht waagerecht</translation>
    </message>
    <message>
        <location filename="../orient.py" line="364"/>
        <location filename="../orient.py" line="479"/>
        <source>the edge does not lie on the bed</source>
        <translation>die Kante liegt nicht auf dem Bett; wähle zusätzlich die Fläche, die auf das Bett soll</translation>
    </message>
    <message>
        <location filename="../orient.py" line="374"/>
        <source>the part cannot stand on this edge</source>
        <translation>das Teil kann nicht auf dieser Kante stehen</translation>
    </message>
    <message>
        <location filename="../orient.py" line="392"/>
        <source>the part cannot rest on this face</source>
        <translation>das Teil kann nicht auf dieser Fläche liegen, andere Teile davon reichen tiefer</translation>
    </message>
    <message>
        <location filename="../orient.py" line="416"/>
        <source>the rim has no flat face to stand on</source>
        <translation>der Rand hat keine ebene Fläche, auf der das Teil stehen kann</translation>
    </message>
    <message>
        <location filename="../orient.py" line="440"/>
        <source>the two faces point in opposite directions</source>
        <translation>die beiden Flächen zeigen in entgegengesetzte Richtungen</translation>
    </message>
    <message>
        <location filename="../orient.py" line="458"/>
        <source>the part cannot rest between these faces</source>
        <translation>das Teil kann nicht zwischen diesen Flächen aufliegen, andere Teile davon reichen tiefer</translation>
    </message>
    <message>
        <location filename="../orient.py" line="481"/>
        <source>an edge alone stands the part only at 45 degrees; for another angle select the face that is to lie on the bed</source>
        <translation>eine Kante allein stellt das Teil nur bei 45 Grad auf; für einen anderen Winkel wähle zusätzlich die Fläche, die auf das Bett soll</translation>
    </message>
    <message>
        <location filename="../orient.py" line="469"/>
        <source>the edge is not an edge of the selected face</source>
        <translation>die Kante gehört nicht zur gewählten Fläche</translation>
    </message>
    <message>
        <location filename="../orient.py" line="485"/>
        <source>a rounded face does not lie on the bed with its edge; select it alone, or the two faces beside it</source>
        <translation>eine gewölbte Fläche liegt nicht mit ihrer Kante auf dem Bett; wähle sie allein oder die beiden Flächen daneben</translation>
    </message>
    <message>
        <location filename="../limits.py" line="91"/>
        <location filename="../params.py" line="84"/>
        <source>%s is not a finite number</source>
        <translation>%s ist keine endliche Zahl</translation>
    </message>
    <message>
        <location filename="../limits.py" line="94"/>
        <source>%s must lie between %.0f and %.0f degrees</source>
        <translation>%s muss zwischen %.0f und %.0f Grad liegen</translation>
    </message>
    <message>
        <location filename="../limits.py" line="97"/>
        <source>overhang_unprintable must not be steeper than overhang_critical</source>
        <translation>overhang_unprintable darf nicht steiler sein als overhang_critical</translation>
    </message>
    <message>
        <location filename="../limits.py" line="101"/>
        <source>%s must be 0 or greater</source>
        <translation>%s muss 0 oder größer sein</translation>
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
        <translation>der Zinkenabstand muss 0 (berührend) oder größer sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="102"/>
        <source>foot_overhang must be 0 or greater</source>
        <translation>Fußüberstand muss 0 oder größer sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="104"/>
        <source>brim_width must be 0 (no brim) or greater</source>
        <translation>brim_width muss 0 (kein Brim) oder größer sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="106"/>
        <source>bead_width is less than half the nozzle diameter</source>
        <translation>die Bahnbreite ist kleiner als der halbe Düsendurchmesser</translation>
    </message>
    <message>
        <location filename="../params.py" line="108"/>
        <source>layer_height is greater than the nozzle diameter</source>
        <translation>die Schichthöhe ist größer als der Düsendurchmesser</translation>
    </message>
    <message>
        <location filename="../params.py" line="110"/>
        <source>tine_layers must be at least 1</source>
        <translation>Zinkenschichten müssen mindestens 1 sein</translation>
    </message>
    <message>
        <location filename="../params.py" line="112"/>
        <source>tine_width_beads must be at least 1</source>
        <translation>Zinkenbreite in Bahnen muss mindestens 1 sein</translation>
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
        <translation>Finnenanzahl muss mindestens 1 sein</translation>
    </message>
    <message>
        <location filename="../shapes.py" line="87"/>
        <source>%s has no shape</source>
        <translation>%s hat keine Form</translation>
    </message>
    <message>
        <location filename="../handles.py" line="529"/>
        <source>No 3D view of %s is open to edit the fins in.</source>
        <translation>Von %s ist keine 3D-Ansicht offen, in der die Finnen bearbeitet werden können.</translation>
    </message>
    <message>
        <location filename="../check.py" line="34"/>
        <source>Stability check of %s</source>
        <translation>Standfestigkeit von %s</translation>
    </message>
    <message>
        <location filename="../check.py" line="35"/>
        <source>Part check of %s</source>
        <translation>Prüfung von %s</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="39"/>
        <source>Check limits</source>
        <translation>Prüfgrenzen</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="49"/>
        <source>Overhangs</source>
        <translation>Überhänge</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="50"/>
        <source>Critical below</source>
        <translation>Kritisch unter</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="51"/>
        <source>Faces lying flatter than this from the bed, without fins, are critical and marked yellow. 0 degrees is a face lying flat over the bed, 90 a vertical wall, as PrusaSlicer measures its overhang threshold; Cura measures from the vertical, its value is 90 degrees less.</source>
        <translation>Flächen ohne Finnen, die flacher als dieser Winkel zur Bettebene liegen, sind kritisch und werden gelb markiert. 0 Grad ist eine Fläche, die flach über dem Bett liegt, 90 Grad eine senkrechte Wand, so wie PrusaSlicer seine Überhangschwelle misst; Cura misst von der Senkrechten aus, sein Wert ist um 90 Grad kleiner.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="56"/>
        <source>Not printable below</source>
        <translation>Nicht druckbar unter</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="57"/>
        <source>Faces lying flatter than this from the bed, without fins, are too flat to print and marked red. At most the critical limit.</source>
        <translation>Flächen ohne Finnen, die flacher als dieser Winkel zur Bettebene liegen, sind zu flach zum Drucken und werden rot markiert. Höchstens so groß wie die kritische Grenze.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="60"/>
        <source>Least area</source>
        <translation>Mindestfläche</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="61"/>
        <source>Overhanging faces smaller than this, like the corner facets of a chamfer, are bridged over by the slicer and not reported.</source>
        <translation>Überhängende Flächen, die kleiner sind, etwa die Eckflächen einer Fase, überbrückt der Slicer; sie werden nicht gemeldet.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="65"/>
        <source>Stability</source>
        <translation>Standfestigkeit</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="66"/>
        <source>At risk of tipping below</source>
        <translation>Kippgefährdet unter</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="67"/>
        <source>The tipping margin: how far the plumb line from the centre of mass lies inside the edge of the footprint. Closer than this, the part is at risk of tipping and shown yellow; outside the footprint it tips, shown red.</source>
        <translation>Der Kippabstand: wie weit das Lot vom Schwerpunkt innerhalb des Rands der Standfläche liegt. Liegt es näher am Rand, ist das Teil kippgefährdet und wird gelb gezeigt; außerhalb der Standfläche kippt es, rot gezeigt.</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="75"/>
        <source>Strictness</source>
        <translation>Strenge</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="76"/>
        <source>Strict</source>
        <translation>Streng</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="77"/>
        <source>Normal</source>
        <translation>Normal</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="78"/>
        <source>Custom</source>
        <translation>Eigene</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="79"/>
        <source>How strictly the checks rate a part. Normal, built in, allows for what common printers manage and for the grip of the first layer on the bed. Strict counts the geometry alone: what would need support is not printable, and the part needs a wider tipping margin. Custom: the limits set below by hand.</source>
        <translation>Wie streng die Prüfungen ein Teil bewerten. Normal, eingebaut, rechnet mit dem, was gängige Drucker schaffen, und mit der Haftung der ersten Schicht auf dem Bett. Streng zählt nur die Geometrie: was eine Stütze bräuchte, ist nicht druckbar, und das Teil braucht einen größeren Kippabstand. Eigene: die unten von Hand gesetzten Grenzen.</translation>
    </message>
</context>
<context>
    <name>FinSnap_AddCounterFin</name>
    <message>
        <location filename="../commands.py" line="769"/>
        <source>Add counter fin</source>
        <translation>Gegenfinne hinzufügen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="770"/>
        <source>Adds a fin on the opposite side of existing fins, against tipping away, as large as the main fin; fewer counter tines in the panel make it smaller. Select the fins: the face leaning the other way is found automatically. Or select a face of the part as well to choose it yourself. To remove the counter fin, clear its face in the property view.</source>
        <translation>Fügt vorhandenen Finnen eine Finne auf der Gegenseite hinzu, gegen Wegkippen, so groß wie die Hauptfinne; weniger Zinken der Gegenfinne in der Maske machen sie kleiner. Die Finnen auswählen: Die zur anderen Seite geneigte Fläche wird automatisch gefunden. Oder zusätzlich eine Fläche des Bauteils auswählen, um sie selbst festzulegen. Zum Entfernen die Fläche der Gegenfinne in der Eigenschaftenansicht leeren.</translation>
    </message>
</context>
<context>
    <name>FinSnap_AddFins</name>
    <message>
        <location filename="../commands.py" line="737"/>
        <source>Add fins</source>
        <translation>Finnen hinzufügen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="738"/>
        <source>Select the face that leans over the bed; optionally a second face on the opposite side for a counter fin</source>
        <translation>Die Fläche auswählen, die über das Bett ragt; optional eine zweite Fläche auf der Gegenseite für eine Gegenfinne</translation>
    </message>
</context>
<context>
    <name>FinSnap_CheckPart</name>
    <message>
        <location filename="../commands.py" line="1062"/>
        <source>Check part</source>
        <translation>Teil prüfen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="1063"/>
        <source>Checks the selected part, with or without fins, as it stands, for everything that keeps it from printing, all at once: faces overhanging without fins, islands, where it would start printing in the air, and whether it stays standing while it is printed. Says what it found and keeps it as a part check in the tree, which shows it all: the eye shows or hides it, deleting the check removes it. Once the part, its place or its fins change, the check is marked out of date; double-click it to check again.</source>
        <translation>Prüft das ausgewählte Teil, mit oder ohne Finnen, so wie es steht, auf einmal auf alles, was den Druck verhindert: Flächen, die ohne Finnen überhängen, Inseln, wo es in der Luft zu drucken beginnen würde, und ob es während des Drucks stehen bleibt. Sagt, was gefunden wurde, und legt es als Prüfung im Baum ab, die alles anzeigt: das Auge blendet es ein und aus, Löschen der Prüfung entfernt es. Ändern sich das Teil, seine Lage oder seine Finnen, wird die Prüfung als veraltet markiert; zum erneuten Prüfen doppelklicken.</translation>
    </message>
</context>
<context>
    <name>FinSnap_CheckStability</name>
    <message>
        <location filename="../commands.py" line="1008"/>
        <source>Check stability</source>
        <translation>Standfestigkeit prüfen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="1009"/>
        <source>Checks whether the selected part stays standing while it is printed, layer by layer, as it grows and its centre of mass moves: first on its own, then, where it would tip over, held by its fins, which hold it only from their lowest tine up. Says at which layer it would tip and which way. Keeps it as a stability check in the tree, which shows the part coloured by height, the layer it tips at and the plumb line from its centre of mass to the bed: the eye shows or hides them, deleting the check removes them. Once the part, its place or its fins change, the check is marked out of date; double-click it to check again.</source>
        <translation>Prüft Schicht für Schicht, ob das ausgewählte Teil während des Drucks stehen bleibt, während es wächst und sein Schwerpunkt wandert: zuerst allein, dann, wo es umkippen würde, von seinen Finnen gehalten, die es erst ab ihrer untersten Zinke halten. Sagt, bei welcher Schicht es kippen würde und wohin. Legt es als Standfestigkeitsprüfung im Baum ab, die das Teil nach Höhe eingefärbt, die Schicht, an der es kippt, und das Lot von seinem Schwerpunkt zum Bett zeigt: das Auge blendet sie ein und aus, Löschen der Prüfung entfernt sie. Ändern sich das Teil, seine Lage oder seine Finnen, wird die Prüfung als veraltet markiert; zum erneuten Prüfen doppelklicken.</translation>
    </message>
</context>
<context>
    <name>FinSnap_Export3MF</name>
    <message>
        <location filename="../commands.py" line="919"/>
        <source>Export 3MF</source>
        <translation>3MF exportieren</translation>
    </message>
    <message>
        <location filename="../commands.py" line="920"/>
        <source>Export the selection to 3MF, every body as its own object for the slicer. With nothing selected, all fins of the document are exported together with their parts.</source>
        <translation>Die Auswahl als 3MF exportieren, jeden Körper als eigenes Objekt für den Slicer. Ist nichts ausgewählt, werden alle Finnen des Dokuments mit ihren Bauteilen exportiert.</translation>
    </message>
</context>
<context>
    <name>FinSnap_ExportSTEP</name>
    <message>
        <location filename="../commands.py" line="943"/>
        <source>Export STEP</source>
        <translation>STEP exportieren</translation>
    </message>
    <message>
        <location filename="../commands.py" line="944"/>
        <source>Export the selection to STEP, with exact surfaces instead of a mesh. The slicer loads it as one object with a part per body: split it into objects there, so part and fins are printed separately. With nothing selected, all fins of the document are exported together with their parts.</source>
        <translation>Die Auswahl als STEP exportieren, mit exakten Flächen statt eines Netzes. Der Slicer lädt sie als ein Objekt mit einem Teil je Körper: dort in Objekte trennen, damit Bauteil und Finnen getrennt gedruckt werden. Ist nichts ausgewählt, werden alle Finnen des Dokuments mit ihren Bauteilen exportiert.</translation>
    </message>
</context>
<context>
    <name>FinSnap_IslandsWhileEditing</name>
    <message>
        <location filename="../commands.py" line="1085"/>
        <source>Islands while editing</source>
        <translation>Inseln beim Bearbeiten</translation>
    </message>
    <message>
        <location filename="../commands.py" line="1086"/>
        <source>While on, fins check their part for islands as they are made and edited, and Quick fins prefers ways to stand it without. Off, they are not checked then, which keeps a large part quick on a slow computer; Check part checks them at the end.</source>
        <translation>Ist es an, prüfen Finnen ihr Teil beim Erstellen und Bearbeiten auf Inseln, und Schnelle Finnen bevorzugt Aufstellungen ohne. Ist es aus, wird dann nicht geprüft, was ein großes Teil auf einem langsamen Rechner flüssig hält; Teil prüfen prüft sie am Ende.</translation>
    </message>
</context>
<context>
    <name>FinSnap_LayFlat</name>
    <message>
        <location filename="../commands.py" line="439"/>
        <source>Lay flat again</source>
        <translation>Wieder flach legen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="440"/>
        <source>Puts a part stood on an edge back as it lay before. Select the part or its fins. If the part has fins, it asks whether to delete them; kept fins move along with the part and are rebuilt once it is moved again. Deleting the last fins of a part lays it flat as well.</source>
        <translation>Legt ein auf eine Kante gestelltes Teil wieder so hin, wie es vorher lag. Wähle das Teil oder seine Finnen. Hat das Teil Finnen, wird gefragt, ob sie gelöscht werden; behaltene Finnen bewegen sich mit dem Teil und werden neu gebaut, sobald es wieder bewegt wird. Das Löschen der letzten Finnen eines Teils legt es ebenfalls flach.</translation>
    </message>
</context>
<context>
    <name>FinSnap_MeshToSolid</name>
    <message>
        <location filename="../commands.py" line="815"/>
        <source>Mesh to solid</source>
        <translation>Netz zu Volumenkörper</translation>
    </message>
    <message>
        <location filename="../commands.py" line="816"/>
        <source>Turn a selected STL mesh into a solid with planar faces, so fins can be added</source>
        <translation>Ein ausgewähltes STL-Netz in einen Volumenkörper mit ebenen Flächen umwandeln, damit Finnen hinzugefügt werden können</translation>
    </message>
</context>
<context>
    <name>FinSnap_QuickFins</name>
    <message>
        <location filename="../commands.py" line="516"/>
        <source>Quick fins</source>
        <translation>Schnelle Finnen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="517"/>
        <source>Stands the part up and adds one fin in the middle of a face in one step, then opens the panel to adjust it. Select the edge the part is to stand on: the fins go under the largest face that leans over the bed. Or select the face the fins are to support: the part is turned so that it leans 45 degrees over the bed, on its longest edge; select one of its edges as well to stand on that one, or, after the face, a chamfer or fillet to rest on. A chamfer or fillet alone, or the two faces beside a fillet, carry the part as well. The rim or the curved side of a cylinder or tube stands it on its rim, with one fin under its lowest line. A counter fin, where wanted, is added in the panel. Where the part can stand on another edge, or the fins can go under another face, a table at the top of the panel lists them to choose from; ways where the part would start printing in the air are left out while one without is found.</source>
        <translation>Stellt das Teil auf und setzt in einem Schritt eine Finne in die Mitte einer Fläche, dann öffnet sich die Maske zum Anpassen. Wähle die Kante, auf der das Teil stehen soll: Die Finnen kommen unter die größte Fläche, die über das Bett hängt. Oder wähle die Fläche, die gestützt werden soll: Das Teil wird so gedreht, dass sie mit 45 Grad über dem Bett hängt, auf ihrer längsten Kante; wähle zusätzlich eine ihrer Kanten, um auf dieser zu stehen, oder nach der Fläche eine Fase oder Rundung, auf der das Teil liegen soll. Eine Fase oder Rundung allein oder die beiden Flächen neben einer Rundung tragen das Teil ebenfalls. Der Rand oder die gewölbte Seite eines Zylinders oder Rohrs stellt es auf seinen Rand, mit einer Finne unter seiner untersten Linie. Eine Gegenfinne fügst du bei Bedarf in der Maske hinzu. Kann das Teil auch auf einer anderen Kante stehen oder passen die Finnen auch unter eine andere Fläche, listet eine Tabelle oben in der Maske diese Möglichkeiten zur Auswahl auf; Möglichkeiten, bei denen das Teil in der Luft zu drucken beginnen würde, werden weggelassen, solange es eine ohne gibt.</translation>
    </message>
</context>
<context>
    <name>FinSnap_Tilt</name>
    <message>
        <location filename="../commands.py" line="310"/>
        <source>Stand on edge</source>
        <translation>Auf Kante stellen</translation>
    </message>
    <message>
        <location filename="../commands.py" line="311"/>
        <source>Select an edge of the part and the face of that edge that is to lie on the bed. The face is laid onto the bed, the part is turned about the edge by the tilt angle and set back onto the bed, standing on the edge. For an edge already on the bed, the edge alone is enough; so it is for an edge between two flat faces at a right angle, on which the part stands at 45 degrees. A face alone, a chamfer or a fillet, is laid onto the bed and carries the part: a chamfer lies flat on it, a fillet touches it along its middle. Two faces alone, such as the two beside a fillet, stand the part on what joins them, both equally steep. The rim of a cylinder or tube stands it on that rim, leaning to the front.</source>
        <translation>Wähle eine Kante des Teils und die Fläche dieser Kante, die auf dem Bett liegen soll. Die Fläche wird auf das Bett gelegt, das Teil um den Kippwinkel um die Kante gedreht und wieder auf das Bett gesetzt, sodass es auf der Kante steht. Liegt die Kante schon auf dem Bett, genügt die Kante allein; ebenso bei einer Kante zwischen zwei ebenen Flächen im rechten Winkel, auf der das Teil dann mit 45 Grad steht. Eine Fläche allein, eine Fase oder eine Verrundung, wird auf das Bett gelegt und trägt das Teil: eine Fase liegt flach auf, eine Verrundung berührt das Bett entlang ihrer Mitte. Zwei Flächen allein, etwa die beiden neben einer Verrundung, stellen das Teil auf das, was sie verbindet, beide gleich steil. Der Rand eines Zylinders oder Rohrs stellt es auf diesen Rand, nach vorn geneigt.</translation>
    </message>
</context>
<context>
    <name>Workbench</name>
    <message>
        <location filename="../init_gui.py" line="17"/>
        <source>FinSnap</source>
        <translation>FinSnap</translation>
    </message>
    <message>
        <location filename="../init_gui.py" line="18"/>
        <source>Breakaway fins for parts printed standing on an edge</source>
        <translation>Abbrechbare Finnen für Bauteile, die auf einer Kante stehend gedruckt werden</translation>
    </message>
</context>
</TS>
