// Create text parameter pDataFolder with the absolute path to data/bi_handoff.
// Create one query per table, replacing the name below.
(tableName as text) as table =>
let
    Source = Csv.Document(
        File.Contents(pDataFolder & "/" & tableName & ".csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    NonEmpty = Table.SelectRows(Headers, each List.NonNullCount(Record.FieldValues(_)) > 0)
in
    NonEmpty
